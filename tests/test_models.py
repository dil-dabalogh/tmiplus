from tmiplus.core.models import Member, Pool


def test_member_capacity() -> None:
    m = Member(name="X", pool=Pool.Feature, contracted_hours=20)
    assert abs(m.weekly_capacity_pw - 0.5) < 1e-6
