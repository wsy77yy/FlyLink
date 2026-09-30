import logging

from django.db import transaction

from apps.users.models import PilotProfile

from .models import JobApplication, JobPost


logger = logging.getLogger('flylink.jobs')


def ai_match_score(job: JobPost, pilot: PilotProfile) -> float:
    score = 50.0
    if job.license_req and job.license_req.lower() in (pilot.license_level or '').lower():
        score += 25
    elif not job.license_req:
        score += 10
    skill_set = set(pilot.skills or [])
    tag_set = set(job.tags or [])
    if skill_set and tag_set:
        score += len(skill_set & tag_set) / max(len(tag_set), 1) * 25
    score += min(pilot.years_exp, 10) * 1.5
    return round(min(score, 100), 2)


@transaction.atomic
def recommend_pilots(*, job):
    locked_job = JobPost.objects.select_for_update().get(pk=job.pk)
    if locked_job.status != JobPost.Status.OPEN:
        return []
    applications = []
    for pilot_profile in PilotProfile.objects.select_related('user').all()[:50]:
        score = ai_match_score(locked_job, pilot_profile)
        if score < 55:
            continue
        application, _ = JobApplication.objects.get_or_create(
            job=locked_job,
            pilot=pilot_profile.user,
            defaults={
                'match_score': score,
                'status': JobApplication.Status.RECOMMENDED,
                'source': JobApplication.Source.AI,
            },
        )
        applications.append(application)
    logger.info(
        'job_candidates_recommended',
        extra={'job_id': locked_job.pk, 'candidate_count': len(applications)},
    )
    return applications


@transaction.atomic
def create_job_post(*, enterprise, validated_data):
    job = JobPost.objects.create(
        enterprise=enterprise,
        status=JobPost.Status.OPEN,
        **validated_data,
    )
    recommend_pilots(job=job)
    return job
