#!/usr/bin/env python3
from __future__ import annotations

from trust_zone_classifier import classify_trust_zone


def main() -> int:
    trusted = classify_trust_zone(title='Improve README wording', target_files=['README.md'], risk_level='low')
    assert trusted['zone'] == 'trusted'
    assert trusted['standard_mode'] == 'auto'

    docs = classify_trust_zone(title='Update docs guide', target_files=['docs/guide.md'], risk_level='low')
    assert docs['zone'] == 'trusted'
    assert docs['autopilot_mode'] == 'auto'

    guarded = classify_trust_zone(title='Change public API response', target_files=['src/api/routes.py'], risk_level='medium')
    assert guarded['zone'] == 'guarded'
    assert guarded['standard_mode'] == 'preview'
    assert guarded['autopilot_mode'] == 'auto'
    assert guarded['requires_checkpoint'] is True

    blocked = classify_trust_zone(title='Update production deployment secret', target_files=['.env'], risk_level='low')
    assert blocked['zone'] == 'blocked'
    assert blocked['standard_mode'] == 'needs_attention'
    assert blocked['autopilot_mode'] == 'needs_attention'

    high = classify_trust_zone(title='Change database migration', target_files=['migrations/001.sql'], risk_level='high')
    assert high['zone'] == 'blocked'
    print('autopilot trust zone tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
