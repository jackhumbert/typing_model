"""Inline layouts.json into report_template.html -> report.html."""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(HERE, 'layouts.json')) as f:
    data = json.load(f)
with open(os.path.join(HERE, 'report_template.html')) as f:
    tpl = f.read()

start = tpl.index('/*__DATA__*/')
end = tpl.index('/*__END__*/') + len('/*__END__*/')
out = tpl[:start] + json.dumps(data) + tpl[end:]

with open(os.path.join(HERE, 'report.html'), 'w') as f:
    f.write(out)
print('wrote report.html', len(out), 'bytes')
