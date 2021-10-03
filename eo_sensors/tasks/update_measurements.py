from eo_sensors.models import CoverageMask, Sources
from eo_sensors.utils import generate_measurements
from jobs.utils import job
from scopes.models import Scope


@job("processing")
def update_scope_measurements(job):
    scope_id = job.kwargs["scope_id"]

    scope = Scope.objects.get(pk=scope_id)

    # Process first masks from all sources except PS1
    coverage_masks = CoverageMask.objects.exclude(source=Sources.PS1).all()
    generate_measurements(coverage_masks=coverage_masks, scopes=[scope])

    # Now process PS1 masks with simplify=3
    coverage_masks = CoverageMask.objects.filter(source=Sources.PS1).all()
    generate_measurements(coverage_masks=coverage_masks, scopes=[scope], simplify=3.0)
