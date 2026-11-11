"""Deploy a built app to its Cloud Run slot with Cloud Build running as golden-builder (devops' recipe,
arc-eng/hq#781). The connector only uploads the source and starts the build; it holds no deploy rights itself."""

from __future__ import annotations

import os
import time
import uuid

PROJECT = os.environ.get("GCP_PROJECT", "academic-diode-513117-v1")
REGION = "us-west1"
BUCKET = f"{PROJECT}_cloudbuild"
BUILDER_SA = f"projects/{PROJECT}/serviceAccounts/golden-builder@{PROJECT}.iam.gserviceaccount.com"
APP_SA = f"golden-app@{PROJECT}.iam.gserviceaccount.com"
IMAGE_REPO = f"{REGION}-docker.pkg.dev/{PROJECT}/golden-sandbox"
URL = "https://{slot}-42301619537.us-west1.run.app"
EMPTY_DIR = os.path.join(os.path.dirname(__file__), "empty_app")
BUILD_TIMEOUT = 600


class DeployError(Exception):
    pass


def _build(source_tgz: str, slot: str, tag: str) -> str:
    from google.cloud import storage
    from google.cloud.devtools import cloudbuild_v1 as cb

    obj = f"source/{tag}.tgz"
    storage.Client(project=PROJECT).bucket(BUCKET).blob(obj).upload_from_filename(source_tgz)
    image = f"{IMAGE_REPO}/{slot}:{tag}"
    build = cb.Build(
        source=cb.Source(storage_source=cb.StorageSource(bucket=BUCKET, object_=obj)),
        service_account=BUILDER_SA,
        options=cb.BuildOptions(logging=cb.BuildOptions.LoggingMode.CLOUD_LOGGING_ONLY),
        steps=[
            cb.BuildStep(name="gcr.io/cloud-builders/docker", args=["build", "-t", image, "."]),
            cb.BuildStep(name="gcr.io/cloud-builders/docker", args=["push", image]),
            cb.BuildStep(
                name="gcr.io/google.com/cloudsdktool/cloud-sdk:slim",
                entrypoint="gcloud",
                args=["run", "deploy", slot, f"--image={image}", f"--region={REGION}", f"--service-account={APP_SA}", "--max-instances=1", "--quiet"],
            ),
        ],
        images=[image],
        timeout={"seconds": BUILD_TIMEOUT},
    )
    client = cb.CloudBuildClient()
    op = client.create_build(request=cb.CreateBuildRequest(parent=f"projects/{PROJECT}/locations/{REGION}", project_id=PROJECT, build=build))
    build_id = op.metadata.build.id
    name = f"projects/{PROJECT}/locations/{REGION}/builds/{build_id}"
    deadline = time.time() + BUILD_TIMEOUT + 60
    while time.time() < deadline:
        b = client.get_build(request=cb.GetBuildRequest(name=name, project_id=PROJECT, id=build_id))
        if b.status == cb.Build.Status.SUCCESS:
            return build_id
        if b.status in (cb.Build.Status.FAILURE, cb.Build.Status.INTERNAL_ERROR, cb.Build.Status.TIMEOUT, cb.Build.Status.CANCELLED, cb.Build.Status.EXPIRED):
            raise DeployError(f"cloud build {b.status.name.lower()}: {(b.status_detail or '')[:200]} (build {build_id})")
        time.sleep(5)
    raise DeployError(f"cloud build still running after {BUILD_TIMEOUT}s (build {build_id})")


def deploy(source_tgz: str, slot: str) -> tuple[str, str]:
    """Build and deploy `source_tgz` (app code + Dockerfile) to Cloud Run service `slot`. Returns its public URL and the
    Cloud Build id (for the details page's "Last build" link)."""
    tag = f"{slot}-{uuid.uuid4().hex[:8]}"
    try:
        build_id = _build(source_tgz, slot, tag)
    except DeployError:
        raise
    except Exception as e:  # noqa: BLE001
        raise DeployError(f"{type(e).__name__}: {str(e)[:200]}") from e
    return URL.format(slot=slot), build_id


def clear(slot: str) -> None:
    """Put the empty page on `slot` (we may not delete services; devops' note)."""
    import tarfile
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".tgz", delete=False) as f:
        with tarfile.open(f.name, "w:gz") as t:
            t.add(EMPTY_DIR, arcname=".")
        deploy(f.name, slot)
    os.unlink(f.name)
