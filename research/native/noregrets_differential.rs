// Test harness only. engine/cards/eval are imported directly from pinned source
// by the Python driver; this wrapper neither implements nor repairs poker rules.
use std::io::{self, BufRead};
use engine::{Hand, HandConfig, PlayerAction};

fn snapshot(h: &Hand) -> String {
    let n = h.num_players();
    if h.is_terminal() {
        return format!("{{\"terminal\":true,\"returns\":{:?},\"commits\":{:?}}}",
            &h.utilities()[..n], (0..n).map(|p| h.hand_commit(p)).collect::<Vec<_>>());
    }
    let p = h.to_act();
    let prior = h.hand_commit(p) - h.street_commit(p);
    let (lo, hi) = h.raise_bounds().map_or(("null".to_string(), "null".to_string()),
        |(a,b)| ((a+prior).to_string(), (b+prior).to_string()));
    format!(concat!("{{\"terminal\":false,\"actor\":{},\"street\":{},\"board\":{:?},",
        "\"pot\":{},\"commits\":{:?},\"stacks\":{:?},\"folded\":{:?},",
        "\"all_in\":{:?},\"call\":{},\"fold\":{},\"min\":{},\"max\":{}}}"),
        p, h.street() as u8, h.board(), h.pot(),
        (0..n).map(|q| h.hand_commit(q)).collect::<Vec<_>>(),
        (0..n).map(|q| h.stack(q)).collect::<Vec<_>>(),
        (0..n).map(|q| h.folded(q)).collect::<Vec<_>>(),
        (0..n).map(|q| h.all_in(q)).collect::<Vec<_>>(),
        h.to_call().min(h.stack(p)), !h.can_check(), lo, hi)
}

fn main() {
    for line in io::stdin().lock().lines() {
        let values: Vec<u32> = line.unwrap().split_whitespace().map(|x| x.parse().unwrap()).collect();
        let n = values[0] as usize;
        let mut deck = [0u8;52];
        for (i, card) in deck.iter_mut().enumerate() { *card = values[1+n+i] as u8; }
        let cfg = HandConfig {num_players:n, ..HandConfig::default()};
        let mut h = Hand::new_with_stacks(&cfg, if n==2 {0} else {n-1}, deck, &values[1..1+n]);
        let mut states = vec![snapshot(&h)];
        for &a in &values[1+n+52..] {
            if h.is_terminal() {break;}
            let p = h.to_act();
            let prior = h.hand_commit(p) - h.street_commit(p);
            let legal = match a {
                0 => !h.can_check(), 1 => true,
                _ => h.raise_bounds().is_some_and(|(lo,hi)| a>=prior+lo && a<=prior+hi),
            };
            if !legal { states.push(format!("{{\"error\":\"illegal action\",\"action\":{}}}", a)); break; }
            h.apply(match a {0=>PlayerAction::Fold, 1=>PlayerAction::CheckCall, _=>PlayerAction::RaiseTo(a-prior)});
            states.push(snapshot(&h));
        }
        println!("[{}]",states.join(","));
    }
}
