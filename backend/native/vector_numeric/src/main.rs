//! Isolated numeric bridge, never an arbitrary command or file interface.
use std::io::{self, Read, Write};

fn response(token: &str, record: bool) -> Result<String, &'static str> {
    let value: serde_json::Value = serde_json::from_str(token).map_err(|_| "invalid_number")?;
    let serde_json::Value::Number(number) = value else {
        return Err("invalid_number");
    };
    if number.is_f64() {
        let f = number.as_f64().ok_or("invalid_number")?;
        if !f.is_finite() {
            return Err("invalid_number");
        }
        Ok(format!("ok\tf64\t{:016x}", f.to_bits()))
    } else if record || token.starts_with('-') {
        Ok(format!(
            "ok\ti64\t{}",
            number.as_i64().ok_or("invalid_number")?
        ))
    } else {
        Ok(format!(
            "ok\tu64\t{}",
            number.as_u64().ok_or("invalid_number")?
        ))
    }
}

fn handle(line: &str) -> Result<String, &'static str> {
    let (operation, payload) = line.split_once('\t').ok_or("invalid_request")?;
    if payload.contains('\t') {
        return Err("invalid_request");
    }
    match operation {
        "record_f64" => {
            if payload.len() != 16
                || !payload
                    .bytes()
                    .all(|c| c.is_ascii_digit() || (b'a'..=b'f').contains(&c))
            {
                return Err("invalid_input");
            }
            let bits = u64::from_str_radix(payload, 16).map_err(|_| "invalid_input")?;
            let f = f64::from_bits(bits);
            if !f.is_finite() {
                return Err("invalid_input");
            }
            // Python/PyO3 already supplied f64; DO NOT parse a Python JSON token first.
            let token = serde_json::to_string(&f).map_err(|_| "invalid_input")?;
            response(&token, true).map_err(|_| "invalid_input")
        }
        "record_i64" => {
            let i = payload.parse::<i64>().map_err(|_| "invalid_input")?;
            if i.to_string() != payload {
                return Err("invalid_input");
            }
            let token = serde_json::to_string(&i).map_err(|_| "invalid_input")?;
            response(&token, true).map_err(|_| "invalid_input")
        }
        "where" => response(payload, false).map_err(|_| "invalid_filter"),
        _ => Err("invalid_request"),
    }
}

fn main() -> io::Result<()> {
    // One bounded request, one bounded response, then exit. Python scalar JSON
    // is <= 310 integer bytes, or a short finite binary64 token. Larger integer
    // tokens necessarily exceed the parser finite domain and are rejected first.
    let mut bytes = Vec::with_capacity(385);
    io::stdin().take(385).read_to_end(&mut bytes)?;
    let result = if bytes.len() > 384 {
        Err("invalid_request")
    } else {
        std::str::from_utf8(&bytes)
            .map_err(|_| "invalid_request")
            .and_then(|line| handle(line.strip_suffix('\n').unwrap_or(line)))
    };
    let mut output = io::BufWriter::new(io::stdout().lock());
    match result {
        Ok(row) => writeln!(output, "{row}")?,
        Err(code) => writeln!(output, "err\t{code}\t-")?,
    }
    output.flush()
}
