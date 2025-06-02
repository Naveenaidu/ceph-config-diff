from git import Repo
import tempfile
from pathlib import Path
import re
import yaml
import json

# Constants for Ceph repository and folder paths
CEPH_UPSTREAM_REMOTE_URL = "https://github.com/ceph/ceph.git"
CEPH_CONFIG_OPTIONS_FOLDER_PATH = "src/common/options"
REF_CLONE_FOLDER = "/ref-config/"
CMP_CLONE_FOLDER = "cmp-config"


def git_show_yaml_files(hexsha: str):
    file_path = CEPH_CONFIG_OPTIONS_FOLDER_PATH
    res = git_cmd.show("%s:%s" % (hexsha, file_path))
    yaml_files = [line.strip() for line in res.splitlines() if line.endswith(".yaml.in")]

    config_options = {}
    for file in yaml_files:
        yaml_file_path = file_path + "/" + file
        yaml_file_content = res = git_cmd.show("%s:%s" % (hexsha, yaml_file_path))
        try:
            file_content = re.sub(r"@.*@.*", r'"\g<0>"', yaml_file_content)
            config_options[file] = yaml.safe_load(file_content)
        except yaml.YAMLError as excep:
            print(excep)

    return config_options


ref_config_tmp_dir = tempfile.TemporaryDirectory(delete=False)

repo = Repo.clone_from(
    url=CEPH_UPSTREAM_REMOTE_URL,
    to_path=ref_config_tmp_dir.name,
    multi_options=["--sparse", "--single-branch", "--branch=main", "--filter=blob:none", "--no-checkout", "--depth=1"]
)

git_cmd = repo.git
# git_cmd.fetch("origin", "squid:squid", "tentacle:tentacle", "--depth=1")
git_cmd.fetch("origin", "refs/tags/v19.1.0:refs/tags/v19.1.0", "refs/tags/v19.1.1:refs/tags/v19.1.1", "--depth=1")

git_cmd.sparse_checkout("add", CEPH_CONFIG_OPTIONS_FOLDER_PATH)
git_cmd.checkout()

config_options = {}

print("----- refs/tags/v19.1.0 --------")
config_options = git_show_yaml_files("refs/tags/v19.1.0")
print(json.dumps(config_options))

print("----- refs/tags/v19.1.1 --------")
config_options = git_show_yaml_files("refs/tags/v19.1.1")
print(json.dumps(config_options))
print(ref_config_tmp_dir.name)

repo.close()
ref_config_tmp_dir.cleanup()
