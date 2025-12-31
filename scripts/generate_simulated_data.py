#!/usr/bin/env python3
"""Generate simulated history data for visual testing of the dashboard."""

from src.site_generator.history import load_history, append_run, save_history
from src.site_generator.badges import write_badges
import json
import os


def make_cases(status):
    """Generate test case results based on provider status."""
    # All case IDs: multipart (1,2,5,6,7,8) + single-part (9,10,11,12)
    case_ids = ['case_1', 'case_2', 'case_5', 'case_6', 'case_7', 'case_8',
                'case_9', 'case_10', 'case_11', 'case_12']

    if status == 'error':
        # Error status means we couldn't run any tests
        return {}

    if status == 'pass':
        # All tests pass
        cases = {}
        for case_id in case_ids:
            if case_id in ['case_7', 'case_12']:
                # Control groups expect acceptance
                cases[case_id] = {'status': 'pass', 'expected': 'accepted', 'actual': 'accepted', 'error_message': None}
            elif case_id == 'case_8':
                # List parts verification
                cases[case_id] = {'status': 'pass', 'expected': 'parts match', 'actual': 'parts match', 'error_message': None}
            else:
                # Rejection tests
                cases[case_id] = {'status': 'pass', 'expected': 'rejected', 'actual': 'rejected', 'error_message': None}
        return cases

    if status == 'fail':
        # Simulate a failure scenario: some enforcement tests fail
        cases = {}
        for case_id in case_ids:
            if case_id in ['case_7', 'case_12']:
                cases[case_id] = {'status': 'pass', 'expected': 'accepted', 'actual': 'accepted', 'error_message': None}
            elif case_id == 'case_8':
                cases[case_id] = {'status': 'pass', 'expected': 'parts match', 'actual': 'parts match', 'error_message': None}
            elif case_id in ['case_1', 'case_9']:
                # These enforcement tests fail (provider accepted when should reject)
                cases[case_id] = {'status': 'fail', 'expected': 'rejected', 'actual': 'accepted', 'error_message': None}
            else:
                cases[case_id] = {'status': 'pass', 'expected': 'rejected', 'actual': 'rejected', 'error_message': None}
        return cases

    return {}


def make_run(date, providers):
    """Create a run result structure with provider data."""
    return {
        'timestamp': f'{date}T06:00:00Z',
        'providers': {
            key: {
                'name': name,
                'status': status,
                'cases': make_cases(status),
                'duration_seconds': 8.5,
                'error_message': 'Connection timeout' if status == 'error' else None
            }
            for key, (name, status) in providers.items()
        },
        'summary': {
            'total_providers': len(providers),
            'passed': sum(1 for _, s in providers.values() if s == 'pass'),
            'failed': sum(1 for _, s in providers.values() if s == 'fail')
        }
    }


def main():
    # Start fresh
    history = {'last_updated': None, 'providers': {}, 'changelog': []}

    # 30-day scenario with realistic provider names
    # - aws: stable pass throughout
    # - b2: starts failing, recovers on day 10
    # - r2: starts passing, fails day 15-20, recovers
    # - gcs: transient errors on days 5, 12, 25
    runs = [
        # Week 1: Initial tests
        ('2025-01-01', {'aws': ('AWS S3', 'pass'), 'b2': ('Backblaze B2', 'fail'), 'r2': ('Cloudflare R2', 'pass'), 'gcs': ('Google Cloud Storage', 'pass')}),
        ('2025-01-02', {'aws': ('AWS S3', 'pass'), 'b2': ('Backblaze B2', 'fail'), 'r2': ('Cloudflare R2', 'pass'), 'gcs': ('Google Cloud Storage', 'pass')}),
        ('2025-01-03', {'aws': ('AWS S3', 'pass'), 'b2': ('Backblaze B2', 'fail'), 'r2': ('Cloudflare R2', 'pass'), 'gcs': ('Google Cloud Storage', 'pass')}),
        ('2025-01-04', {'aws': ('AWS S3', 'pass'), 'b2': ('Backblaze B2', 'fail'), 'r2': ('Cloudflare R2', 'pass'), 'gcs': ('Google Cloud Storage', 'pass')}),
        ('2025-01-05', {'aws': ('AWS S3', 'pass'), 'b2': ('Backblaze B2', 'fail'), 'r2': ('Cloudflare R2', 'pass'), 'gcs': ('Google Cloud Storage', 'error')}),
        ('2025-01-06', {'aws': ('AWS S3', 'pass'), 'b2': ('Backblaze B2', 'fail'), 'r2': ('Cloudflare R2', 'pass'), 'gcs': ('Google Cloud Storage', 'pass')}),
        ('2025-01-07', {'aws': ('AWS S3', 'pass'), 'b2': ('Backblaze B2', 'fail'), 'r2': ('Cloudflare R2', 'pass'), 'gcs': ('Google Cloud Storage', 'pass')}),
        # Week 2: B2 recovers
        ('2025-01-08', {'aws': ('AWS S3', 'pass'), 'b2': ('Backblaze B2', 'fail'), 'r2': ('Cloudflare R2', 'pass'), 'gcs': ('Google Cloud Storage', 'pass')}),
        ('2025-01-09', {'aws': ('AWS S3', 'pass'), 'b2': ('Backblaze B2', 'fail'), 'r2': ('Cloudflare R2', 'pass'), 'gcs': ('Google Cloud Storage', 'pass')}),
        ('2025-01-10', {'aws': ('AWS S3', 'pass'), 'b2': ('Backblaze B2', 'pass'), 'r2': ('Cloudflare R2', 'pass'), 'gcs': ('Google Cloud Storage', 'pass')}),
        ('2025-01-11', {'aws': ('AWS S3', 'pass'), 'b2': ('Backblaze B2', 'pass'), 'r2': ('Cloudflare R2', 'pass'), 'gcs': ('Google Cloud Storage', 'pass')}),
        ('2025-01-12', {'aws': ('AWS S3', 'pass'), 'b2': ('Backblaze B2', 'pass'), 'r2': ('Cloudflare R2', 'pass'), 'gcs': ('Google Cloud Storage', 'error')}),
        ('2025-01-13', {'aws': ('AWS S3', 'pass'), 'b2': ('Backblaze B2', 'pass'), 'r2': ('Cloudflare R2', 'pass'), 'gcs': ('Google Cloud Storage', 'pass')}),
        ('2025-01-14', {'aws': ('AWS S3', 'pass'), 'b2': ('Backblaze B2', 'pass'), 'r2': ('Cloudflare R2', 'pass'), 'gcs': ('Google Cloud Storage', 'pass')}),
        # Week 3: R2 starts failing
        ('2025-01-15', {'aws': ('AWS S3', 'pass'), 'b2': ('Backblaze B2', 'pass'), 'r2': ('Cloudflare R2', 'fail'), 'gcs': ('Google Cloud Storage', 'pass')}),
        ('2025-01-16', {'aws': ('AWS S3', 'pass'), 'b2': ('Backblaze B2', 'pass'), 'r2': ('Cloudflare R2', 'fail'), 'gcs': ('Google Cloud Storage', 'pass')}),
        ('2025-01-17', {'aws': ('AWS S3', 'pass'), 'b2': ('Backblaze B2', 'pass'), 'r2': ('Cloudflare R2', 'fail'), 'gcs': ('Google Cloud Storage', 'pass')}),
        ('2025-01-18', {'aws': ('AWS S3', 'pass'), 'b2': ('Backblaze B2', 'pass'), 'r2': ('Cloudflare R2', 'fail'), 'gcs': ('Google Cloud Storage', 'pass')}),
        ('2025-01-19', {'aws': ('AWS S3', 'pass'), 'b2': ('Backblaze B2', 'pass'), 'r2': ('Cloudflare R2', 'fail'), 'gcs': ('Google Cloud Storage', 'pass')}),
        ('2025-01-20', {'aws': ('AWS S3', 'pass'), 'b2': ('Backblaze B2', 'pass'), 'r2': ('Cloudflare R2', 'pass'), 'gcs': ('Google Cloud Storage', 'pass')}),
        ('2025-01-21', {'aws': ('AWS S3', 'pass'), 'b2': ('Backblaze B2', 'pass'), 'r2': ('Cloudflare R2', 'pass'), 'gcs': ('Google Cloud Storage', 'pass')}),
        # Week 4: Stable with one more GCS hiccup
        ('2025-01-22', {'aws': ('AWS S3', 'pass'), 'b2': ('Backblaze B2', 'pass'), 'r2': ('Cloudflare R2', 'pass'), 'gcs': ('Google Cloud Storage', 'pass')}),
        ('2025-01-23', {'aws': ('AWS S3', 'pass'), 'b2': ('Backblaze B2', 'pass'), 'r2': ('Cloudflare R2', 'pass'), 'gcs': ('Google Cloud Storage', 'pass')}),
        ('2025-01-24', {'aws': ('AWS S3', 'pass'), 'b2': ('Backblaze B2', 'pass'), 'r2': ('Cloudflare R2', 'pass'), 'gcs': ('Google Cloud Storage', 'pass')}),
        ('2025-01-25', {'aws': ('AWS S3', 'pass'), 'b2': ('Backblaze B2', 'pass'), 'r2': ('Cloudflare R2', 'pass'), 'gcs': ('Google Cloud Storage', 'error')}),
        ('2025-01-26', {'aws': ('AWS S3', 'pass'), 'b2': ('Backblaze B2', 'pass'), 'r2': ('Cloudflare R2', 'pass'), 'gcs': ('Google Cloud Storage', 'pass')}),
        ('2025-01-27', {'aws': ('AWS S3', 'pass'), 'b2': ('Backblaze B2', 'pass'), 'r2': ('Cloudflare R2', 'pass'), 'gcs': ('Google Cloud Storage', 'pass')}),
        ('2025-01-28', {'aws': ('AWS S3', 'pass'), 'b2': ('Backblaze B2', 'pass'), 'r2': ('Cloudflare R2', 'pass'), 'gcs': ('Google Cloud Storage', 'pass')}),
        ('2025-01-29', {'aws': ('AWS S3', 'pass'), 'b2': ('Backblaze B2', 'pass'), 'r2': ('Cloudflare R2', 'pass'), 'gcs': ('Google Cloud Storage', 'pass')}),
        ('2025-01-30', {'aws': ('AWS S3', 'pass'), 'b2': ('Backblaze B2', 'pass'), 'r2': ('Cloudflare R2', 'pass'), 'gcs': ('Google Cloud Storage', 'pass')}),
    ]

    # Build history by appending each run
    for date, providers in runs:
        run = make_run(date, providers)
        history = append_run(history, run)

    # Get the last run for latest.json
    last_date, last_providers = runs[-1]
    latest = make_run(last_date, last_providers)

    # Write files
    output_dir = 'site/data'
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(f'{output_dir}/badges', exist_ok=True)

    # Save history
    save_history(history, f'{output_dir}/history.json')

    # Save latest
    with open(f'{output_dir}/latest.json', 'w') as f:
        json.dump(latest, f, indent=2)

    # Generate badges
    write_badges(latest['providers'], f'{output_dir}/badges')

    print('Generated simulated data:')
    print(f'  - {len(history["providers"])} providers')
    print(f'  - {len(history["changelog"])} changelog entries')
    print(f'  - 30 history entries per provider')
    print()
    print('Changelog entries (chronological):')
    for entry in reversed(history['changelog']):
        print(f'  [{entry["date"]}] {entry["message"]}')


if __name__ == '__main__':
    main()
