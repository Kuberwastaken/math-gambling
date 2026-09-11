//! Same bounded mg114-offset-v1 domain and canonical receipts as search_core.py.
//! See docs/NATIVE_KERNEL.md for bounds; overflow checks stay on in release.
use num_bigint::BigInt;
use num_traits::{Signed, Zero};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::sync::OnceLock;

pub const ENGINE: &str = "mg114-offset-v1";
const D0: i128 = 10_000_000_000_000_000_000 / 54;
const PRIMES: [i64; 15] = [5, 7, 11, 13, 17, 19, 23, 31, 37, 41, 43, 47, 53, 59, 61];
const NAMES: [&str; 12] = [
    "generators",
    "outside_shell",
    "invalid_d",
    "signed_excluded",
    "noninvertible",
    "curves",
    "quotient_points",
    "rejected_mod243",
    "rejected_parity",
    "rejected_prime",
    "exact_tests",
    "hits",
];
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Task {
    pub version: u8,
    pub engine: String,
    pub context: String,
    pub row: String,
    pub block: u32,
}
struct Context {
    ell: i128,
    radius: i128,
    tlo: i128,
    thi: i128,
    dlo: i128,
    dhi: i128,
    low: i128,
    high: i128,
}
fn context(task: &Task) -> Result<(Context, i128), String> {
    if task.version != 1 || task.engine != ENGINE {
        return Err("unsupported engine/version".into());
    }
    if task.context.len() != 3
        || !task.context.starts_with('c')
        || !task.context[1..].bytes().all(|b| b.is_ascii_digit())
    {
        return Err("invalid context".into());
    }
    let i: usize = task.context[1..].parse().map_err(|_| "invalid context")?;
    if i >= 81 {
        return Err("unknown context".into());
    }
    if task.row.is_empty()
        || task.row.len() > 15
        || !task.row.bytes().all(|b| b.is_ascii_digit())
        || (task.row.len() > 1 && task.row.starts_with('0'))
    {
        return Err("noncanonical row".into());
    }
    let row: i128 = task.row.parse().map_err(|_| "invalid row")?;
    let (radius, tlo, thi) = [
        (6_000_000, 8, 31),
        (1_500_000, 128, 511),
        (375_000, 2048, 8191),
    ][i / 9 % 3];
    let (low, high) = [(0, 64), (64, 256), (256, 4096)][i % 3];
    let c = Context {
        ell: [1, 5, 25][i / 27],
        radius,
        tlo,
        thi,
        dlo: D0 * (1 << (i / 3 % 3)),
        dhi: D0 * (1 << (i / 3 % 3 + 1)),
        low,
        high,
    };
    if row >= (2 * radius + 1).pow(2)
        || row % 128 != 0
        || i128::from(task.block) >= (thi - tlo + 16) / 16
    {
        return Err("task outside fixed bounds".into());
    }
    Ok((c, row))
}
fn inv(a: i128, m: i128) -> Option<i128> {
    let (mut r, mut nr, mut t, mut nt) = (m, a.rem_euclid(m), 0, 1);
    while nr != 0 {
        let q = r / nr;
        (r, nr) = (nr, r - q * nr);
        (t, nt) = (nt, t - q * nt);
    }
    if r == 1 {
        Some(t.rem_euclid(m))
    } else {
        None
    }
}
/// Montgomery REDC for odd moduli strictly below 2^63. Wrapping here is
/// intentional arithmetic modulo 2^64, never arithmetic on search integers.
pub struct Montgomery {
    m: u64,
    negative_inverse: u64,
    r2: u64,
}
impl Montgomery {
    pub fn new(m: u64) -> Self {
        assert!(m > 1 && m % 2 == 1 && m < (1 << 63));
        let mut x = 1u64;
        for _ in 0..6 {
            x = x.wrapping_mul(2u64.wrapping_sub(m.wrapping_mul(x)));
        }
        let r = ((1u128 << 64) % u128::from(m)) as u64;
        Self {
            m,
            negative_inverse: x.wrapping_neg(),
            r2: (u128::from(r) * u128::from(r) % u128::from(m)) as u64,
        }
    }
    fn reduce(&self, t: u128) -> u64 {
        let u = (t as u64).wrapping_mul(self.negative_inverse);
        let v = ((t + u128::from(u) * u128::from(self.m)) >> 64) as u64;
        if v >= self.m {
            v - self.m
        } else {
            v
        }
    }
    fn mul(&self, a: u64, b: u64) -> u64 {
        self.reduce(u128::from(a) * u128::from(b))
    }
    pub fn cube(&self, x: u64) -> u64 {
        assert!(x < self.m);
        let x = self.mul(x, self.r2);
        self.reduce(u128::from(self.mul(self.mul(x, x), x)))
    }
}
fn cube_mod(r: i128, d: i128, mont: bool) -> i128 {
    if mont && d % 2 == 1 {
        return i128::from(Montgomery::new(d as u64).cube(r as u64));
    }
    (r * r % d) * r % d
}
struct Filters {
    allowed: Vec<Vec<i64>>,
    masks: Vec<Vec<u64>>,
}
fn filters(k: i128) -> Filters {
    let mut pairs = vec![vec![false; 243]; 243];
    for x in 0i128..243 {
        for y in 0i128..243 {
            pairs[((x + y) % 243) as usize][((x * x * x + y * y * y) % 243) as usize] = true;
        }
    }
    let allowed = (0..243)
        .map(|s| {
            (0i128..243)
                .filter(|z| pairs[s][(k - z * z * z).rem_euclid(243) as usize])
                .map(|z| z as i64)
                .collect()
        })
        .collect();
    let masks = PRIMES
        .iter()
        .map(|&p| {
            let mut qr = vec![false; p as usize];
            for x in 0..p {
                qr[(x * x % p) as usize] = true;
            }
            (0..p)
                .map(|s| {
                    (0..p)
                        .filter(|&z| {
                            qr[(3 * s * (4 * k as i64 - 4 * z * z * z - s * s * s)).rem_euclid(p)
                                as usize]
                        })
                        .fold(0u64, |mask, z| mask | (1 << z))
                })
                .collect()
        })
        .collect();
    Filters { allowed, masks }
}
static FILTERS: OnceLock<Filters> = OnceLock::new();
// Big integers are deliberately confined to the rare final test and identity.
// z^3 can exceed 128 bits in the public domain. Never truncate it.
pub fn candidate(k: i128, s: i128, z: i128, minimal: bool) -> Option<Vec<String>> {
    if s == 0 {
        return None;
    }
    let (s, z) = (BigInt::from(s), BigInt::from(z));
    let n: BigInt = 4 * (BigInt::from(k) - z.pow(3)) - s.pow(3);
    let den: BigInt = 3 * &s;
    let square: BigInt = &n / &den;
    if !(&n % &den).is_zero() || square.is_negative() {
        return None;
    }
    let v = BigInt::from(square.to_biguint()?.sqrt());
    if &v * &v != square || !((&s + &v) % BigInt::from(2)).is_zero() {
        return None;
    }
    let x: BigInt = (&s + &v) / 2;
    let y: BigInt = (&s - &v) / 2;
    if minimal && (z.abs() > x.abs() || z.abs() > y.abs()) {
        return None;
    }
    assert_eq!(x.pow(3) + y.pow(3) + z.pow(3), BigInt::from(k));
    Some(vec![x.to_string(), y.to_string(), z.to_string()])
}
fn scan(
    k: i128,
    d: i128,
    r: i128,
    qlo: i128,
    qhi: i128,
    f: &Filters,
    counts: &mut [u64; 12],
    mut hit: impl FnMut(Value),
) {
    let s = if d % 3 == 2 * (k / 3 % 3) % 3 { d } else { -d };
    counts[5] += 1;
    counts[6] += (qhi - qlo + 1) as u64;
    let inverse = inv(d % 243, 243).unwrap();
    let mut qs = Vec::new();
    for &zm in &f.allowed[s.rem_euclid(243) as usize] {
        let residue = ((i128::from(zm) - r) * inverse).rem_euclid(243);
        let mut q = qlo + (residue - qlo).rem_euclid(243);
        while q <= qhi {
            qs.push(q as i64);
            q += 243;
        }
    }
    qs.sort_unstable();
    counts[7] += (qhi - qlo + 1) as u64 - qs.len() as u64;
    // Reduce the large integers once per curve. The inner sieve uses only
    // small signed integers; |q|<=4097 and p<=61.
    let residues: Vec<_> = PRIMES
        .iter()
        .enumerate()
        .map(|(j, &p)| {
            (
                p,
                r.rem_euclid(p as i128) as i64,
                d.rem_euclid(p as i128) as i64,
                f.masks[j][s.rem_euclid(p as i128) as usize],
            )
        })
        .collect();
    for q in qs {
        if (k - s - r - d * i128::from(q)).rem_euclid(2) != 0 {
            counts[8] += 1;
            continue;
        }
        if residues
            .iter()
            .any(|&(p, rp, dp, mask)| mask >> (rp + dp * q).rem_euclid(p) & 1 == 0)
        {
            counts[9] += 1;
            continue;
        }
        counts[10] += 1;
        if let Some(xyz) = candidate(k, s, r + d * i128::from(q), true) {
            counts[11] += 1;
            hit(json!({"xyz":xyz,"D":d.to_string(),"r":r.to_string(),"q":q.to_string()}));
        }
    }
}
fn shell(
    base: i128,
    ell: i128,
    lo: i128,
    hi: i128,
    lower: i128,
    upper: i128,
    constant: i128,
    linear: i128,
) -> (i128, i128) {
    let norm = |t| {
        let a = base + ell * t;
        a * a * a - linear * a + constant
    };
    let (a0, a1) = (base + ell * lo, base + ell * hi);
    let n0 = norm(lo);
    assert_eq!(n0 % ell, 0);
    let minabs = if a0 >= 0 {
        a0
    } else if a1 <= 0 {
        -a1
    } else {
        0
    };
    if 3 * minabs * minabs < linear {
        return (lo, hi);
    }
    let n1 = norm(hi);
    if n1 <= lower || n0 > upper {
        return (lo, lo - 1);
    }
    let (mut first, mut last) = (lo, hi);
    if n0 <= lower {
        let (mut l, mut r) = (lo + 1, hi);
        while l < r {
            let m = (l + r) / 2;
            if norm(m) <= lower {
                l = m + 1;
            } else {
                r = m;
            }
        }
        first = l;
    }
    if n1 > upper {
        let (mut l, mut r) = (first, hi);
        while l < r {
            let m = (l + r) / 2;
            if norm(m) <= upper {
                l = m + 1;
            } else {
                r = m;
            }
        }
        last = l - 1;
    }
    (first, last)
}
pub fn run(task: Task, mont: bool, mut on_hit: impl FnMut(&Value)) -> Result<Value, String> {
    let (c, start) = context(&task)?;
    let f = FILTERS.get_or_init(|| filters(114));
    let mut counts = [0u64; 12];
    let mut hits = Vec::new();
    for row in start..(start + 128).min((2 * c.radius + 1).pow(2)) {
        let width = 2 * c.radius + 1;
        let b = row % width - c.radius;
        let cc = row / width - c.radius;
        let residue = (-4 * b - 16 * cc).rem_euclid(c.ell);
        let numerator = -4_848_807_585_839_879_338 * b
            - 23_510_935_004_498_358_840 * cc
            - residue * 1_000_000_000_000_000_000;
        let denominator = c.ell * 1_000_000_000_000_000_000;
        let base = residue + c.ell * (2 * numerator + denominator).div_euclid(2 * denominator);
        let tlo = c.tlo + 16 * i128::from(task.block);
        let thi = (tlo + 15).min(c.thi);
        let constant = 114 * b * b * b + 12996 * cc * cc * cc;
        let linear = 342 * b * cc;
        let (first, last) = shell(
            base,
            c.ell,
            tlo,
            thi,
            c.ell * c.dlo,
            c.ell * c.dhi,
            constant,
            linear,
        );
        counts[0] += (thi - tlo + 1) as u64;
        counts[1] += (thi - tlo + 1 - (last - first + 1).max(0)) as u64;
        for t in first..=last {
            let a = base + c.ell * t;
            let n = a * a * a - linear * a + constant;
            assert_eq!(n % c.ell, 0);
            let d = n / c.ell;
            if !(c.dlo < d && d <= c.dhi) {
                counts[1] += 1;
                continue;
            }
            if d < 2 || d % 3 == 0 {
                counts[2] += 1;
                continue;
            }
            let s = if d % 3 == 1 { d } else { -d };
            if [0, 4, 6].contains(&s.rem_euclid(8))
                || [0, 19, 76, 95, 114, 133, 171, 209, 304, 323].contains(&s.rem_euclid(361))
            {
                counts[3] += 1;
                continue;
            }
            let big_b = 114 * cc * cc - a * b;
            let big_c = b * b - a * cc;
            let Some(inverse) = inv(big_c, d) else {
                counts[4] += 1;
                continue;
            };
            let r = (big_b.rem_euclid(d) * inverse).rem_euclid(d);
            assert_eq!(cube_mod(r, d, mont), 114 % d);
            let zmin = 100_000_000_000_000_000i128.max(c.low * d);
            let zmax = c.high * d;
            let (qlo, qhi) = if s < 0 {
                ((zmin - r).div_euclid(d) + 1, (zmax - r).div_euclid(d))
            } else {
                (-((zmax + r) / d), -((zmin + r) / d) - 1)
            };
            scan(114, d, r, qlo, qhi, f, &mut counts, |mut h| {
                h["abc"] = json!([a.to_string(), b.to_string(), cc.to_string()]);
                h["t"] = json!(t as i64);
                h["row"] = json!(row.to_string());
                on_hit(&h);
                hits.push(h);
            });
        }
    }
    assert_eq!(counts[0], counts[1..6].iter().sum::<u64>());
    assert_eq!(counts[6], counts[7..11].iter().sum::<u64>());
    let counters: serde_json::Map<String, Value> = NAMES
        .iter()
        .zip(counts)
        .map(|(n, v)| (n.to_string(), json!(v)))
        .collect();
    let id = format!("{}:{}:{}:{}", ENGINE, task.context, task.row, task.block);
    let mut result = json!({"task":task,"id":id,"counters":counters,"hits":hits});
    let digest = format!("{:x}", Sha256::digest(serde_json::to_vec(&result).unwrap()));
    result["digest"] = json!(digest);
    Ok(result)
}

/// Test/benchmark-only API, never an accepted public task or bank namespace.
pub fn regression(k: i128, d: i128, r: i128, qlo: i128, qhi: i128) -> Value {
    assert!((3..=1000).contains(&k) && [3, 6].contains(&(k % 9)));
    assert!(d >= 2 && d <= D0 * 8 && d % 3 != 0 && (0..d).contains(&r));
    assert!(qlo >= -4097 && qhi <= 4097 && qhi >= qlo && qhi - qlo <= 8192);
    assert_eq!(cube_mod(r, d, false), k % d);
    let mut counts = [0; 12];
    let mut hits = Vec::new();
    scan(k, d, r, qlo, qhi, &filters(k), &mut counts, |h| {
        hits.push(h)
    });
    json!({"counters":NAMES.iter().zip(counts).map(|(n,v)|(n.to_string(),json!(v))).collect::<serde_json::Map<String,Value>>(),"hits":hits})
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn montgomery_matches_wide_division() {
        let mut state = 114u64;
        for i in 0..20000 {
            state = state.wrapping_mul(6364136223846793005).wrapping_add(1);
            let d = if i % 3 == 0 {
                (1u64 << 63) - 1
            } else {
                (state % ((1u64 << 63) - 2) + 3) | 1
            };
            let r = state % d;
            let m = Montgomery::new(d);
            let r128 = u128::from(r);
            let d128 = u128::from(d);
            assert_eq!(u128::from(m.cube(r)), ((r128 * r128 % d128) * r128) % d128);
        }
    }
    #[test]
    fn final_check_exceeds_128_bits() {
        // Known k=3 representation: its cubes exceed 2^128.
        assert!(candidate(3, 108398887211, -472715493453327032, true).is_some());
        assert!(candidate(3, 108398887211, -472715493453327031, true).is_none());
        let d = D0 * 8;
        // Largest permitted band values must be evaluated without truncation.
        assert!(candidate(114, d, -4096 * d, true).is_none());
        assert!(candidate(114, -d, 4096 * d, true).is_none());
    }
    #[test]
    fn known_positive_curves() {
        for (k, x, y, z) in [
            (39, -159380i128, 134476, 117367i128),
            (84, 41639611, -41531726, -8241191),
            (30, 2220422932, -2218888517, -283059965),
        ] {
            let d = (x + y).abs();
            let r = z.rem_euclid(d);
            let q = (z - r) / d;
            assert_eq!(
                regression(k, d, r, q, q)["hits"].as_array().unwrap().len(),
                1
            );
        }
        assert!(candidate(75, -148, 4381159, true).is_some());
    }
}

#[cfg(target_arch = "wasm32")]
mod wasm {
    use super::*;
    use std::cell::RefCell;
    // One non-shared instance per Web Worker; the host can write only a capped
    // task buffer. No pointers supplied by remote task JSON are dereferenced.
    static mut INPUT: [u8; 2048] = [0; 2048];
    thread_local! { static OUTPUT: RefCell<Vec<u8>> = const { RefCell::new(Vec::new()) }; }
    #[link(wasm_import_module = "mg")]
    extern "C" {
        fn identity(ptr: *const u8, len: usize);
    }
    #[no_mangle]
    pub extern "C" fn mg_self_test() -> u32 {
        (candidate(39, -24904, 117367, true).is_some()
            && candidate(3, 108398887211, -472715493453327032, true).is_some()
            && candidate(3, 108398887211, -472715493453327031, true).is_none()) as u32
    }
    #[no_mangle]
    pub extern "C" fn mg_input_ptr() -> *mut u8 {
        std::ptr::addr_of_mut!(INPUT).cast()
    }
    #[no_mangle]
    pub extern "C" fn mg_run(len: usize, mont: u32) -> usize {
        let result = if len > 2048 {
            Err("task exceeds byte cap".to_string())
        } else {
            let bytes =
                unsafe { std::slice::from_raw_parts(std::ptr::addr_of!(INPUT).cast(), len) };
            serde_json::from_slice::<Task>(bytes)
                .map_err(|e| e.to_string())
                .and_then(|task| {
                    run(task, mont != 0, |hit| {
                        let bytes = serde_json::to_vec(hit).unwrap();
                        unsafe {
                            identity(bytes.as_ptr(), bytes.len());
                        }
                    })
                })
        };
        let value = result.unwrap_or_else(|e| json!({"error":e}));
        OUTPUT.with(|o| {
            let mut o = o.borrow_mut();
            *o = serde_json::to_vec(&value).unwrap();
            o.len()
        })
    }
    #[no_mangle]
    pub extern "C" fn mg_output_ptr() -> *const u8 {
        OUTPUT.with(|o| o.borrow().as_ptr())
    }
}
