#! /usr/bin/env python3

from aas_test_engines import file
import aas_core3.jsonization as aas_jsonization
import aas_core3.verification as aas_verification
from fences.core.util import ConfusionMatrix
from collections import defaultdict
import json
from timeit import default_timer

print("Running generation acceptance tests...")

mat = ConfusionMatrix()
causes = defaultdict(lambda: 0)
DEBUG = False
blacklist = [
    'Message broker must be a model reference to a referable.',
    'Max. interval is not applicable for input direction.',
    'Observed must be a model reference to a referable.',
    'Derived-from must be a model reference to an asset administration shell.',
    'All submodels must be model references to a submodel.',
]

start = default_timer()
for idx, (is_valid, sample) in enumerate(file.generate()):
    try:
        env = aas_jsonization.environment_from_jsonable(sample)
    except aas_jsonization.DeserializationException as e:
        env = None

    if env is None:
        accepted = False
    else:
        accepted = True
        errors = aas_verification.verify(env)
        for error in errors:
            if is_valid:
                causes[error.cause] += 1
            if error.cause not in blacklist:
                accepted = False
    mat.add(is_valid, accepted)
    if DEBUG and not is_valid and accepted:
        with open(f'invalid_accepted/{mat.invalid_accepted}.json', "w") as f:
            json.dump(sample, f, indent=4)

    if (idx+1) % 100 == 0:
        mat.print()

    if not DEBUG and idx > 500:
        break

end = default_timer()

print(f"Elapsed time: {end - start:.1f}s")

if DEBUG:
    for cause in sorted(causes.keys(), key=lambda x: causes[x]):
        print(f"{causes[cause]}: {cause}")

if mat.valid_rejected:
    print("Valid instances have been rejected!")
    exit(1)

 # TODO: need to fix 7 issues in aas-core-python first
if mat.invalid_accepted > 7:
    print("Invalid instances have been accepted!")
    exit(1)

exit(0)
