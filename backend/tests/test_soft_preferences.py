from app.schemas import CandidateProfile, ContextBundle, Fact, JobData
from app.services.job_matcher import match_job


def profile() -> CandidateProfile:
    return CandidateProfile(
        reviewed=True,
        skills=["Python"],
        facts=[Fact(field="skills", value="Python", source="user", verified=True)],
    )


def job(**updates) -> JobData:
    return JobData(
        source="demo",
        external_id="preference-check",
        title="Developer",
        company="Example",
        url="https://example.invalid/job",
        skills=["Python"],
        **updates,
    )


def context() -> ContextBundle:
    result = ContextBundle()
    result.rules.minimum_score = 0
    result.preferences.work_modes = ["remote", "hybrid", "onsite"]
    result.preferences.preferred_cities = ["Bogotá"]
    result.preferences.preferred_contract_types = ["indefinido"]
    result.preferences.relocation_allowed = True
    return result


def test_preferred_city_ranks_higher_without_excluding_relocation():
    local = match_job(profile(), job(work_mode="onsite", location="Bogotá, Colombia"), context())
    other = match_job(profile(), job(work_mode="onsite", location="Medellín, Colombia"), context())
    assert local.eligible and other.eligible
    assert local.score > other.score
    assert not other.blockers


def test_preferred_indefinite_contract_does_not_exclude_better_paid_alternatives():
    permanent = match_job(profile(), job(work_mode="remote", contract_type="permanent"), context())
    alternative = match_job(profile(), job(work_mode="remote", contract_type="contractor"), context())
    assert permanent.eligible and alternative.eligible
    assert permanent.score > alternative.score


def test_full_time_does_not_claim_an_indefinite_contract():
    result = match_job(profile(), job(work_mode="remote", contract_type="full_time"), context())
    assert result.eligible
    assert "Tipo de contrato preferido." not in result.matches
    assert any("contrato por confirmar" in gap for gap in result.gaps)


def test_worldwide_remote_does_not_require_a_city_or_relocation():
    result = match_job(profile(), job(work_mode="remote", location="Worldwide"), context())
    assert result.eligible
    assert not any("movilidad" in gap for gap in result.gaps)


def test_salary_exception_requires_human_review_and_never_allows_automatic_eligibility():
    prefs = context()
    prefs.preferences.minimum_monthly = 5200000
    prefs.preferences.currency = "COP"
    prefs.preferences.salary_below_minimum_requires_review = True
    offer = job(
        work_mode="remote", salary_min=4500000, salary_max=5000000, currency="COP", salary_period="month"
    )
    result = match_job(profile(), offer, prefs)
    assert not result.eligible and result.requires_human_review
    assert any("incrementos" in reason for reason in result.blockers)
    offer.mandatory_requirements = ["Licencia profesional obligatoria"]
    excluded = match_job(profile(), offer, prefs)
    assert not excluded.eligible and not excluded.requires_human_review


def test_desired_salary_ranks_higher_while_higher_offers_are_still_allowed():
    prefs = context()
    prefs.preferences.minimum_monthly = 5200000
    prefs.preferences.desired_monthly = 7000000
    prefs.preferences.desired_monthly_max = 9000000
    prefs.preferences.currency = "COP"
    lower = match_job(
        profile(),
        job(
            work_mode="remote", salary_min=5200000, salary_max=5200000, currency="COP", salary_period="month"
        ),
        prefs,
    )
    desired = match_job(
        profile(),
        job(
            work_mode="remote", salary_min=8000000, salary_max=8000000, currency="COP", salary_period="month"
        ),
        prefs,
    )
    higher = match_job(
        profile(),
        job(
            work_mode="remote",
            salary_min=10000000,
            salary_max=10000000,
            currency="COP",
            salary_period="month",
        ),
        prefs,
    )
    assert lower.eligible and desired.eligible and higher.eligible
    assert desired.score > lower.score


def test_conditional_salary_application_waits_for_information_instead_of_being_rejected(
    client, headers, demo_jobs
):
    from app.database import session as database
    from app.models import Job

    chosen = next(item for item in demo_jobs if item["match"]["eligible"])
    with database.SessionLocal() as db:
        stored = db.get(Job, chosen["id"])
        stored.data = {
            **stored.data,
            "salary_min": 4500000,
            "salary_max": 5000000,
            "currency": "COP",
            "salary_period": "month",
        }
        db.commit()
    bundle = client.get("/api/v1/context").json()
    bundle.pop("version")
    bundle["preferences"].update(
        {"minimum_monthly": 5200000, "currency": "COP", "salary_below_minimum_requires_review": True}
    )
    assert client.put("/api/v1/context", json=bundle).status_code == 200
    response = client.post("/api/v1/applications", json={"job_id": chosen["id"]})
    assert response.status_code == 201, response.text
    assert response.json()["state"] == "NEEDS_INFORMATION"
    assert client.post(f"/api/v1/applications/{response.json()['id']}/approve").status_code == 409
