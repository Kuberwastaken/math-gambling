#!/usr/bin/env python3
"""Full frozen-checker positive corpus, durability, and exact UBSan microtests.

Run with no solution campaign active and coordinate with timing experiments.
This does not rebuild or modify the production worker. Temporary sanitizer
binaries exercise the actual helper source and are deleted after validation.
"""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parent
LAB = ROOT.parent
BINARY = ROOT / 'bin/offset_worker'
HEADERS = LAB.parent.parent / 'work/pari-include'

ROW_TEST = r'''
int main(void){
 init_signed_filters();uint64_t checks=0,jumps=0;
 for(uint64_t ell=1;ell<=25;ell*=5)for(int b=-19;b<=19;b++)for(int c=-19;c<=19;c++){
  offset_row row=make_offset_row(ell,b,c);offset_wheel wheel;make_offset_wheel(&row,&wheel);
  for(int t=0;t<912;t++){
   i128 a=row.base+ell*t,n=a*a*a+row.p*a+row.q,d=n/ell;
   int dm=mod128(d,3),category=0,s=dm==1?1:-1;
   if(!dm)category=1;else if(bad8[mod128(s*d,8)])category=2;else if(bad361[mod128(s*d,361)])category=3;
   int actual=0;for(int k=1;k<4;k++)if(wheel.prefix[k][t%456+1]!=wheel.prefix[k][t%456])actual=k;
   if(actual!=category)fail("Independent wheel category failed");checks++;
  }
  for(int t=8;t<=8191;t+=997){
   i128 a=row.base+ell*t,d=offset_norm(&row,t)/ell,d1=3*a*a+3*ell*a+ell*ell+row.p,d2=6*ell*(a+ell),d3=6*ell*ell;
   int gaps[]={1,2,63,455,456,4096};for(int j=0;j<6;j++)if(t+gaps[j]<=8191){
    i128 x=d,y=d1,z=d2;offset_jump(gaps[j],&x,&y,&z,d3);
    if(x!=offset_norm(&row,t+gaps[j])/ell)fail("Independent jump failed");jumps++;
   }
  }
 }
 printf("{\"wheel_categories\":%llu,\"jumps\":%llu}\n",(unsigned long long)checks,(unsigned long long)jumps);
}
'''

QUOTIENT_TEST = r'''
int main(void){
 uint64_t checked=0;int ks[]={3,6,114,633};
 for(int ki=0;ki<4;ki++){
  long k=ks[ki];init_filters(k);
  for(int d=1;d<243;d++)if(d%3){
   int eps=(k/3)%3,sm=d%3==(2*eps)%3?d:243-d,slot=d-1-d/3;
   for(int pos=0;pos<243;pos++){
    int word=pos/64,bit=pos%64;uint64_t v=short_q_masks[slot][word]>>bit;
    if(bit)v|=short_q_masks[slot][word+1]<<(64-bit);
    for(int b=0;b<64;b++){
     int expected=ok81[sm][d*((pos+b)%243)%243];
     if(((v>>b)&1)!=(unsigned)expected)fail("Cyclic mask differs from direct residue predicate");
     checked++;
    }
   }
  }
 }
 printf("{\"cyclic_mask_bits_checked\":%llu,\"k_values\":4}\n",(unsigned long long)checked);
}
'''


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_success(stdout, expected):
    records = [json.loads(line) for line in stdout.splitlines()]
    assert records and records[-1]['type'] == 'stats'
    stats = records[-1]
    assert stats['complete'] and stats['k'] == expected['k']
    hits = [record for record in records if record['type'] == 'hit']
    expected_xyz = tuple(sorted(expected['xyz']))
    actual = set()
    for hit in hits:
        xyz = tuple(sorted(map(int, hit['xyz'])))
        assert sum(value ** 3 for value in xyz) == expected['k']
        assert hit['k'] == expected['k']
        assert int(hit['D']) == expected['d'] and int(hit['r']) == expected['r']
        z = int(hit['r']) + int(hit['D']) * int(hit['q'])
        assert z in xyz and abs(z) == min(map(abs, xyz))
        actual.add(xyz)
    assert expected_xyz in actual, (expected, hits)
    assert stats['hits'] == len(hits)
    assert stats['quotient_points'] == (
        stats['rejected_mod243'] + stats['rejected_parity'] +
        stats['exact_tests'] + sum(f['rejected'] for f in stats['filters']))
    return stats, len(hits)


def singleton_command(case):
    z = min(case['xyz'], key=abs)
    q, remainder = divmod(z - case['r'], case['d'])
    assert remainder == 0
    return [str(BINARY), 'interval', str(case['k']), str(case['d']),
            str(case['r']), str(q), str(q), 'fixed']


def microtests(tmp):
    source = (ROOT / 'offset_worker.c').read_text()
    source = source.replace('#include "checker.c"',
                            '#include "' + str(ROOT / 'checker.c') + '"')
    source = source.replace('int main(int argc,char **argv){',
                            'int offset_program_main(int argc,char **argv){')
    assert 'int offset_program_main' in source
    tests = [source + ROW_TEST,
             '#define main checker_program_main\n#include "' +
             str(ROOT / 'checker.c') + '"\n#undef main\n' + QUOTIENT_TEST]
    results = []
    for number, code in enumerate(tests):
        cfile = tmp / f'microtest-{number}.c'
        executable = tmp / f'microtest-{number}'
        cfile.write_text(code)
        subprocess.run(['clang', '-O1', '-fsanitize=undefined',
                        '-fno-sanitize-recover=all', '-I', str(HEADERS),
                        str(cfile), '-L', str(LAB / 'bin'), '-lpari',
                        '-o', str(executable)], check=True, timeout=30)
        run = subprocess.run([str(executable)], capture_output=True, text=True,
                             check=True, timeout=30)
        assert not run.stderr, run.stderr
        results.append(json.loads(run.stdout))
    assert results[0] == {'wheel_categories': 4161456, 'jumps': 219024}
    assert results[1] == {'cyclic_mask_bits_checked': 10077696, 'k_values': 4}
    return dict(ubsan=True, **results[0], **results[1])


def main():
    begun = time.monotonic()
    frozen = {str(path.relative_to(LAB)): digest(path) for path in (
        ROOT / 'offset_worker.c', ROOT / 'checker.c', BINARY,
        LAB / 'campaign_worker.c', LAB / 'phase2/offset_worker.c',
        LAB / 'phase2/bin/offset_worker')}
    fixture = LAB / 'data/known-curves.json'
    cases = json.loads(fixture.read_text())['cases']
    assert len(cases) == 661
    cases.append(dict(k=3, xyz=sorted([
        569936821221962380720, -569936821113563493509,
        -472715493453327032]), d=108398887211, r=21397363547, R=5000000))
    total_hits = total_q = total_exact = 0
    records = []
    for index, case in enumerate(cases):
        assert sum(value ** 3 for value in case['xyz']) == case['k']
        z = min(case['xyz'], key=abs)
        assert abs(sum(case['xyz']) - z) == case['d']
        assert z % case['d'] == case['r']
        assert pow(case['r'], 3, case['d']) == case['k'] % case['d']
        command = [str(BINARY), 'curve', *[str(case[key]) for key in
                   ('k', 'd', 'r', 'R')], 'fixed']
        run = subprocess.run(command, capture_output=True, text=True,
                             check=True, timeout=30)
        assert not run.stderr, run.stderr
        stats, hits = parse_success(run.stdout, case)
        total_hits += hits
        total_q += stats['quotient_points']
        total_exact += stats['exact_tests']
        records.append(dict(index=index, k=case['k'], D=case['d'],
                            expected_recovered=True, returned_hits=hits))
    with tempfile.TemporaryDirectory(prefix='phase3-release-') as directory:
        tmp = Path(directory)
        os.symlink(LAB / 'bin/libpari.dylib', tmp / 'libpari.dylib')
        arithmetic = microtests(tmp)
        durability = []
        for case in (cases[0], cases[-1]):
            path = tmp / f"hit-{case['k']}.jsonl"
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC |
                         getattr(os, 'O_SYNC', 0), 0o600)
            try:
                run = subprocess.run(singleton_command(case), stdout=fd,
                                     stderr=subprocess.PIPE, text=True, timeout=30)
            finally:
                os.close(fd)
            assert run.returncode == 0 and not run.stderr, run.stderr
            _, hits = parse_success(path.read_text(), case)
            durability.append(dict(k=case['k'], complete_hit_lines=hits,
                                   regular_file=True, synchronous_open=True,
                                   checked_worker_fsync_path=True))
        # macOS has no /dev/full. A read-only regular descriptor independently
        # exercises the actual failed hit fflush and verifies a nonzero exit.
        readonly = tmp / 'read-only-output'
        readonly.write_text('unchanged sentinel\n')
        with readonly.open('rb') as stream:
            failed = subprocess.run(singleton_command(cases[0]), stdout=stream,
                                    stderr=subprocess.PIPE, text=True, timeout=30)
        assert failed.returncode != 0 and 'Hit stdout flush failed' in failed.stderr
        assert readonly.read_text() == 'unchanged sentinel\n'
        failure = dict(read_only_stdout_exit=failed.returncode,
                       read_only_stdout_error=failed.stderr.strip(),
                       completed_stats_emitted=False)
        if Path('/dev/full').exists():
            with open('/dev/full', 'wb') as stream:
                full = subprocess.run(singleton_command(cases[0]), stdout=stream,
                                      stderr=subprocess.PIPE, text=True, timeout=30)
            assert full.returncode != 0
            failure['dev_full'] = dict(status='passed', exit_code=full.returncode,
                                       error=full.stderr.strip())
        else:
            failure['dev_full'] = dict(status='unavailable',
                                       reason='/dev/full is absent on this host')
    assert all(digest(LAB / name) == value for name, value in frozen.items())
    result = dict(
        status='passed', fixture_count=len(cases), catalogue_cases=661,
        extra_large_k3_regression=True, all_expected_solutions_recovered=True,
        every_returned_cube_identity_independently_verified=True,
        returned_hits=total_hits, quotient_points=total_q, exact_tests=total_exact,
        full_configured_curve_intervals=True, policy='fixed',
        arithmetic_microtests=arithmetic, regular_file_durability=durability,
        stdout_failure=failure, sources_and_binaries_unchanged=True,
        sha256=frozen, fixture_sha256=digest(fixture), validator_sha256=digest(Path(__file__)),
        cases=records, wall_seconds=time.monotonic()-begun,
        scope='Known-positive recovery, exact arithmetic and output handling; no discovery-probability claim')
    (ROOT / 'known-hit-validation.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: value for key, value in result.items() if key != 'cases'}, indent=2))


if __name__ == '__main__':
    main()
