from netscan.profiles import PROFILES, StateProfile


def test_profiles_registry_has_ca_and_ks():
    assert set(PROFILES) >= {"CA", "KS"}
    assert isinstance(PROFILES["CA"], StateProfile)
    assert PROFILES["CA"].gutter == "ca_line_label"
    assert PROFILES["KS"].gutter == "ks_line_numbers"
