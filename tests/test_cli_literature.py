import contextlib
import copy
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.error import URLError

from resistance.cli import main, read_csv, read_json
from resistance.engine import InputError
from resistance.literature import fetch_searches, search_plan

ROOT = Path(__file__).resolve().parents[1]


class CLITests(unittest.TestCase):
    def test_json_and_markdown_example_end_to_end(self):
        for output_format in ('json', 'markdown'):
            result = subprocess.run([sys.executable, '-m', 'resistance', 'assess',
                'examples/combination_progression.json', '--format', output_format], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            if output_format == 'json':
                report = json.loads(result.stdout)
                self.assertEqual(len(report['candidates']), 4)
                self.assertEqual(report['unmatched_findings'][0]['finding_id'], 'pi3k_vus')
            else:
                self.assertIn('PIK3CA_HOTSPOT', result.stdout)
                self.assertIn('not_online_verified', result.stdout)
                self.assertIn('不构成处方', result.stdout)

    def test_csv_context_example_end_to_end(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            status = main(['assess', str(ROOT/'examples/csv_context.json'), '--findings-csv', str(ROOT/'examples/findings.csv')])
        self.assertEqual(status, 0)
        self.assertEqual({x['rule_id'] for x in json.loads(stdout.getvalue())['candidates']}, {'MET_AMPLIFICATION', 'AKT1_E17K'})

    def test_output_existing_file_preserved_and_bad_input_no_report(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)/'report.json'
            output.write_text('user content')
            with contextlib.redirect_stderr(io.StringIO()):
                status = main(['assess', str(ROOT/'examples/plasma_negative.json'), '--out', str(output)])
            self.assertEqual(status, 2)
            self.assertEqual(output.read_text(), 'user content')
            bad = Path(directory)/'bad.json'
            bad.write_text('{"schema_version": "1.0"}')
            output.unlink()
            with contextlib.redirect_stderr(io.StringIO()):
                status = main(['assess', str(bad), '--out', str(output)])
            self.assertEqual(status, 2)
            self.assertFalse(output.exists())

    def test_csv_cannot_silently_replace_existing_findings(self):
        with contextlib.redirect_stderr(io.StringIO()):
            status = main(['assess', str(ROOT/'examples/combination_progression.json'), '--findings-csv', str(ROOT/'examples/findings.csv')])
        self.assertEqual(status, 2)

    def test_duplicate_and_nonfinite_json_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'input.json'
            for value in ('{"gene":"PIK3CA","gene":"AKT1"}', '{"value":NaN}', '{"value":Infinity}'):
                path.write_text(value)
                with self.subTest(value=value), self.assertRaises(InputError):
                    read_json(path)

    def test_csv_boolean_false_is_not_truthy_and_bad_bool_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'input.csv'
            header = 'id,sample_id,gene,alteration,assay,significance,orthogonal_confirmation\n'
            path.write_text(header+'f,p,MET,amplification,FISH,pathogenic,false\n')
            self.assertIs(read_csv(path)[0]['orthogonal_confirmation'], False)
            path.write_text(header+'f,p,MET,amplification,FISH,pathogenic,False\n')
            with self.assertRaises(InputError):
                read_csv(path)

    def test_malformed_duplicate_csv_columns_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'input.csv'
            header = 'id,sample_id,gene,alteration,assay,significance\n'
            for value in [header+'f,p,MET,amplification,FISH,pathogenic,extra\n',
                          header+'f,p,MET\n',
                          'id,sample_id,gene,gene,alteration,assay,significance\n']:
                path.write_text(value)
                with self.subTest(value=value), self.assertRaises(InputError):
                    read_csv(path)


def response(value):
    return io.BytesIO(json.dumps(value).encode())


class LiteratureAcquisitionTests(unittest.TestCase):
    def test_plan_has_eight_groups_and_exact_dates_and_no_case_inputs(self):
        plan = search_plan()
        self.assertEqual(len(plan['queries']), 8)
        self.assertTrue(all('FIRST_PDATE:[2016-10-30 TO 2026-10-30]' in value for value in plan['queries'].values()))
        self.assertIn('Manual ASCO', plan['conference_search'])

    def test_proxy_denial_is_blocked_not_zero_hits_and_stops_retries(self):
        calls = []
        def denied(request, timeout):
            calls.append(request.full_url)
            raise URLError('Tunnel connection failed: 403 Forbidden')
        report = fetch_searches(opener=denied)
        self.assertEqual(report['status'], 'blocked')
        self.assertEqual(len(calls), 1)
        self.assertIsNone(report['results']['01_upstream']['hit_count'])
        self.assertEqual(report['results']['02_pi3k_akt']['status'], 'not_run_after_access_failure')

    def test_zero_results_is_distinguished_from_blocked_search(self):
        report = fetch_searches('01_upstream', opener=lambda *args, **kwargs: response({'hitCount': 0, 'resultList': {'result': []}}))
        self.assertEqual(report['status'], 'metadata_retrieved')
        self.assertEqual(report['results']['01_upstream']['hit_count'], 0)
        self.assertFalse(report['full_text_verified'])
        self.assertFalse(report['registry_automatically_updated'])

    def test_pagination_deduplicates_and_marks_truncation(self):
        pages = [
            {'hitCount': 2, 'nextCursorMark': 'next', 'resultList': {'result': [{'source':'MED','id':'1','title':'one'}]}},
            {'hitCount': 2, 'nextCursorMark': 'end', 'resultList': {'result': [{'source':'MED','id':'1','title':'one'}, {'source':'MED','id':'2','title':'two'}]}}
        ]
        remaining = copy.deepcopy(pages)
        report = fetch_searches('01_upstream', opener=lambda *args, **kwargs: response(remaining.pop(0)))
        self.assertEqual(report['status'], 'metadata_retrieved')
        self.assertEqual(len(report['results']['01_upstream']['records']), 2)
        report = fetch_searches('01_upstream', max_pages=1, opener=lambda *args, **kwargs: response(pages[0]))
        self.assertEqual(report['status'], 'incomplete')
        self.assertEqual(report['results']['01_upstream']['status'], 'truncated_metadata_search')

    def test_invalid_response_not_accepted_as_evidence(self):
        for value in ([], {}, {'hitCount': 1, 'resultList': None}, {'hitCount': '1', 'resultList': {'result': []}}, {'hitCount': 1, 'resultList': {'result': [{'title': 'missing id'}]}}):
            with self.subTest(value=value):
                report = fetch_searches('01_upstream', opener=lambda *args, **kwargs: response(value))
                self.assertEqual(report['status'], 'incomplete')
                self.assertEqual(report['results']['01_upstream']['status'], 'invalid_response')


if __name__ == '__main__':
    unittest.main()
