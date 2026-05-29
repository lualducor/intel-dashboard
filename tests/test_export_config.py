import zipfile
from scripts.export_config import export_config

def test_export_config(tmp_path):
    # Call export_config(out_dir=tmp_path)
    zip_path = export_config(out_dir=tmp_path)
    
    assert zip_path.exists()
    assert zip_path.suffix == ".zip"
    
    with zipfile.ZipFile(zip_path, "r") as z:
        namelist = z.namelist()
        assert "sources.yaml" in namelist
        assert "interests.yaml" in namelist
        # env.redacted only exists if .env exists in PROJECT_DIR
        # We don't necessarily want to force it to exist in tests
