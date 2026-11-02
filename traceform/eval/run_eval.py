"""Validate bundled illustrative fixtures. This command is not a quality benchmark."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from eval.dataset_loader import load_dataset_samples

def validate(version):
    if not version or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in version):
        raise ValueError('Choose a dataset version identifier.')
    samples=load_dataset_samples(version,strict=True)
    if not samples:raise ValueError('No fixtures found.')
    failures=[]
    for sample in samples:
        for claim in sample.ground_truth_claims:
            if claim.expected_source_span not in sample.source_document:
                failures.append({'sample_id':sample.id,'message':'Expected source span is absent.'})
    return {'data_mode':'illustrative_fixture_validation','samples':len(samples),'failures':failures,
        'passed':not failures,'fact_accuracy':None,'hallucination_rate':None,'latency_ms':None,'cost_usd':None}
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--version',default='v1');parser.add_argument('--dry-run',action='store_true')
    args=parser.parse_args()
    if not args.dry_run:parser.error('Live measurement uses the durable /evaluations/execute workflow; use --dry-run to validate fixtures.')
    result=validate(args.version);print(json.dumps(result,indent=2));sys.exit(0 if result['passed'] else 1)
