from genome_workbench.domain.qualifiers import QualifierSet


def test_multi_value_preserved_in_order():
    qs = QualifierSet()
    qs.add("db_xref", "GO:0001")
    qs.add("db_xref", "GO:0002")
    assert qs.get("db_xref") == ["GO:0001", "GO:0002"]


def test_key_order_preserved():
    qs = QualifierSet()
    qs.add("note", "n1")
    qs.add("gene", "g1")
    assert qs.keys() == ["note", "gene"]


def test_flag_qualifier_empty_value():
    qs = QualifierSet()
    qs.add("pseudo")
    assert qs.get("pseudo") == [""]
    assert qs.has("pseudo")


def test_unknown_qualifier_not_dropped_on_copy():
    qs = QualifierSet()
    qs.add("totally_custom_key", "value")
    clone = qs.copy()
    assert clone.get("totally_custom_key") == ["value"]
    assert clone == qs


def test_set_all_replaces_values():
    qs = QualifierSet()
    qs.add("note", "old")
    qs.set_all("note", ["new1", "new2"])
    assert qs.get("note") == ["new1", "new2"]


def test_remove_key():
    qs = QualifierSet()
    qs.add("note", "x")
    qs.remove_key("note")
    assert not qs.has("note")
    assert qs.keys() == []


def test_get_first_none_when_missing():
    qs = QualifierSet()
    assert qs.get_first("missing") is None
