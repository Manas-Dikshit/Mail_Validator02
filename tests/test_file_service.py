import pandas as pd
import pytest

from app.services.file_service import (
    detect_email_column,
    load_dataframe,
    write_output_xlsx,
    build_output_dataframe,
    NoEmailColumnFoundError,
    MultipleEmailColumnsError,
)
from app.models.schemas import EmailValidationResult
from app.models.enums import ValidationStatus


class TestDetectEmailColumn:
    def test_detects_standard_email_header(self):
        assert detect_email_column(["Name", "Email"]) == "Email"

    def test_detects_email_address_header(self):
        assert detect_email_column(["Name", "Company", "Email Address"]) == "Email Address"

    def test_detects_snake_case_header(self):
        assert detect_email_column(["name", "email_address"]) == "email_address"

    def test_detects_email_id_header(self):
        assert detect_email_column(["Name", "Email Id"]) == "Email Id"

    def test_case_insensitive(self):
        assert detect_email_column(["NAME", "EMAIL"]) == "EMAIL"

    def test_explicit_preferred_column(self):
        assert (
            detect_email_column(["Name", "Contact Email", "Work Email"], preferred="Work Email")
            == "Work Email"
        )

    def test_no_email_column_raises(self):
        with pytest.raises(NoEmailColumnFoundError):
            detect_email_column(["Name", "Company", "Phone"])

    def test_multiple_email_columns_raises(self):
        with pytest.raises(MultipleEmailColumnsError):
            detect_email_column(["Name", "Email Address", "Work Email"])


class TestLoadDataframe:
    def test_load_csv(self, tmp_path):
        p = tmp_path / "in.csv"
        p.write_text("Name,Email\nJohn,john@example-mail.com\n")
        df = load_dataframe(p)
        assert list(df.columns) == ["Name", "Email"]
        assert len(df) == 1

    def test_unsupported_extension_raises(self, tmp_path):
        p = tmp_path / "in.txt"
        p.write_text("hello")
        with pytest.raises(ValueError):
            load_dataframe(p)


class TestWriteOutputXlsx:
    def test_writes_file_with_all_columns(self, tmp_path):
        original_df = pd.DataFrame({"Name": ["John"], "Email": ["john@example-mail.com"]})
        result = EmailValidationResult(
            original_email="john@example-mail.com",
            normalized_email="john@example-mail.com",
            validation_status=ValidationStatus.VALID_BUSINESS,
            syntax_valid=True,
        )
        out_df = build_output_dataframe(original_df, "Email", [result])
        assert "Name" in out_df.columns
        assert "Email" in out_df.columns
        assert "Validation Status" in out_df.columns
        assert "Risk Score" in out_df.columns

        out_path = tmp_path / "out.xlsx"
        write_output_xlsx(out_df, out_path)
        assert out_path.exists()

        # round trip
        reloaded = pd.read_excel(out_path)
        assert reloaded.loc[0, "Name"] == "John"
        assert reloaded.loc[0, "Validation Status"] == "VALID_BUSINESS"
