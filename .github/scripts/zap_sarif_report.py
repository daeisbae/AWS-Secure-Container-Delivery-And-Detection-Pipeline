from pathlib import Path


REPORT_DIRECTORY = Path("/zap/wrk")
REPORT_FILE = "zap.sarif.json"


def zap_pre_shutdown(zap):
    """Generate the ZAP report before the packaged scan script stops ZAP."""
    zap.reports.generate(
        title="PipelineSecurity ZAP scan",
        template="sarif-json",
        reportfilename=REPORT_FILE,
        reportdir=str(REPORT_DIRECTORY),
        display=False,
    )

    report_path = REPORT_DIRECTORY / REPORT_FILE
    if not report_path.is_file():
        raise RuntimeError(f"ZAP did not create {report_path}")
