from app.workers.batch_processor import process_emails_batch


class TestBatchProcessor:
    def test_processes_all_rows(self):
        emails = ["a@example-mail.com", "b@example-mail.com", "c@example-mail.com"]
        results, summary = process_emails_batch(emails, check_dns=False)
        assert len(results) == 3
        assert summary.total_rows == 3

    def test_duplicate_detection_case_insensitive(self):
        emails = ["John@Example-Mail.com", "john@example-mail.com", "JOHN@EXAMPLE-MAIL.COM"]
        results, summary = process_emails_batch(emails, check_dns=False)
        assert summary.duplicate_count == 3
        assert all(r.duplicate_count == 3 for r in results)

    def test_preserves_row_order(self):
        emails = ["z@example-mail.com", "a@example-mail.com", "m@example-mail.com"]
        results, _ = process_emails_batch(emails, check_dns=False)
        assert [r.original_email for r in results] == emails

    def test_empty_list(self):
        results, summary = process_emails_batch([], check_dns=False)
        assert results == []
        assert summary.total_rows == 0

    def test_invalid_and_valid_mixed(self):
        emails = ["not-an-email", "valid@example-mail.com"]
        results, summary = process_emails_batch(emails, check_dns=False)
        assert summary.invalid_count == 1
