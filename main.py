#!/usr/bin/env python3

import yaml
import argparse
import subprocess
import glob
import os
import sys
import json
import re

from collections import defaultdict


"""
Things to do:
    - Sparse checkout the files
    - Store all the files in dictionaries, format of this TBD
    - Compare these dicts and generate the report
"""

"""
Modes:
- diff-branch
- diff-commit
- diff-branch-remote-repo

ceph-config-diff --mode diff-branch --ref-repo <repo-url> main squid 
ceph-config-diff --mode diff-commit --ref-repo <repo-url> --ref-branch main sha1 sha2
ceph-config-diff --mode diff-branch-remote-repo --ref-repo <repo-url> --remote-repo <remote-url> --ref-branch <branch> --remote-branch <branch>


--ref-repo = Option, default value is ceph upstream linkModes:
- diff-branch
- diff-commit
- diff-branch-remote-repo

ceph-config-diff --mode diff-branch --ref-repo <repo-url> --ref-branch main --cmp-branch squid 
ceph-config-diff --mode diff-commit --ref-repo <repo-url> --ref-branch main --ref-sha sha1 --cmp-sha sha2
ceph-config-diff --mode diff-branch-remote-repo --ref-repo <repo-url> --remote-repo <remote-url> --ref-branch <branch> --cmp-branch <branch>


--ref-repo = Option, default value is ceph upstream link

python3 main.py diff-branch --ref-branch main --cmp-branch reef
"""

# TODO: Naveen: Fetch these values from a config file
CEPH_UPSTREAM_REMOTE_URL = "https://github.com/ceph/ceph.git"
CEPH_CONFIG_OPTIONS_FOLDER_PATH = "src/common/options"
REF_CLONE_FOLDER = "ref-config"
CMP_CLONE_FOLDER = "cmp-config"

"""
git clone --filter=blob:none --no-checkout --depth 1 --single-branch --branch <branch_name> --sparse <repo_url> <folder_name>
cd ceph
git sparse-checkout add src/common/options
git checkout
"""


def sparse_branch_checkout(
    repo_url: str, branch_name: str, clone_folder_name: str, config_options_path: str
):
    commands = [
        f"rm -rf {clone_folder_name}",
        f"git clone --filter=blob:none --no-checkout --depth 1 --single-branch --branch {branch_name} --sparse {repo_url} {clone_folder_name}",
        f"git sparse-checkout add {config_options_path}",
        "git checkout",
    ]

    # Run the first 2 commands in current directory
    for command in commands[0:2]:
        print(command)
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            text=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
        )
        if result.returncode != 0:
            print(f"Command failed: {command}")
            sys.exit(result.returncode)

    # Run the sparse checkout in cloned directory
    # This is necessary, because we need to use "cwd" to cd into cloned repository
    for command in commands[2:]:
        print(command)
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            text=True,
            cwd=clone_folder_name,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
        )
        if result.returncode != 0:
            print(f"Command failed: {command}")
            sys.exit(result.returncode)


def load_config_yaml_files(path: str):
    files = glob.glob(f"{path}/*.yaml.in")
    config_options = {}

    for file in files:
        with open(file, "r") as stream:
            try:

                # Preprocess the file to enclose template value in double quotes
                # eg: @CEPH_INSTALL_FULL_PKGLIBDIR@/erasure-code -> "@CEPH_INSTALL_FULL_PKGLIBDIR@/erasure-code"
                # This pre-process is okay since these values are dependent on
                # the build system and as such cannot be found out until the
                # entire ceph is built - which is a cumbersome process

                file_content = stream.read()
                # Enclose @key@somemoretext in double quotes "@key@somemoretext"
                file_content = re.sub(r"@.*@.*", r'"\g<0>"', file_content)

                file_name = os.path.basename(file)
                file_config_options = yaml.safe_load(file_content)
                config_options[file_name] = file_config_options

            except yaml.YAMLError as excep:
                print(excep)

    return config_options


# Gets the names of all the configuration option across all daemons
def get_daemons_config_names(daemons, daemon_configs):
    daemons_config_names = defaultdict(list)
    for daemon in daemons:
        daemon_config_options = daemon_configs[daemon]["options"]
        daemon_config_names = set(
            map(lambda config_value: config_value["name"], daemon_config_options)
        )
        daemons_config_names[daemon] = list(daemon_config_names)
    return daemons_config_names


# Get the configuration options that has been modified, Returns a diction in the format:
def get_shared_config_daemon(shared_config_names, ref_daemon_configs, cmp_daemon_configs):
    """
    Returns a diction in the format:

    "modified":{
            "<file-name-1>" :{
                "config-option-1": {
                    "key-1": {
                        "before": "<old-value>",
                        "after": "<new-value>"
                    },
                }
            }
    }
    """
    modified_config = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))
    for config_name in shared_config_names:
        # Get the entire config information for the configuration option
        ref_daemon_config = next(
            filter(
                lambda deamon_config: deamon_config["name"] == config_name,
                ref_daemon_configs,
            ),
            None,
        )
        cmp_daemon_config = next(
            filter(
                lambda deamon_config: deamon_config["name"] == config_name,
                cmp_daemon_configs,
            ),
            None,
        )

        # Get all the keys of a config option (eg: type, level, desc etc)
        ref_daemon_config_keys = set(ref_daemon_config.keys())
        cmp_daemon_config_keys = set(cmp_daemon_config.keys())

        # Get the new config option key that was added
        deleted_config_keys = ref_daemon_config_keys.difference(cmp_daemon_config_keys)

        # Get the config option key that was deleted
        new_config_keys = cmp_daemon_config_keys.difference(ref_daemon_config_keys)

        for config_key in new_config_keys:
            modified_config[config_name][config_key]["before"] = ""
            modified_config[config_name][config_key]["after"] = cmp_daemon_config[
                config_key
            ]

        for config_key in deleted_config_keys:
            modified_config[config_name][config_key]["before"] = ref_daemon_config[
                config_key
            ]
            modified_config[config_name][config_key]["after"] = ""

        shared_config_keys = ref_daemon_config_keys.intersection(cmp_daemon_config_keys)
        for config_key in shared_config_keys:
            if ref_daemon_config[config_key] != cmp_daemon_config[config_key]:
                modified_config[config_name][config_key]["before"] = ref_daemon_config[
                    config_key
                ]
                modified_config[config_name][config_key]["after"] = cmp_daemon_config[
                    config_key
                ]

    return modified_config


def diff_config():
    new_config = defaultdict(list)
    deleted_config = defaultdict(list)
    modified_config = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))

    # Get the configurations options present for all daemons in the "reference" version
    ref_config_dict = load_config_yaml_files(
        f"{REF_CLONE_FOLDER}/{CEPH_CONFIG_OPTIONS_FOLDER_PATH}"
    )
    ref_file_names = set(ref_config_dict.keys())

    # Get the configurations options present for all daemons in the "comparing" version
    config_dict = load_config_yaml_files(f"{CMP_CLONE_FOLDER}/{CEPH_CONFIG_OPTIONS_FOLDER_PATH}")
    cmp_file_names = set(config_dict.keys())

    # Case 1: A deamon is present in "reference" version but has been deleted
    # from "comparing" version
    # (A,B,C) ref - (A,B) cmp == C (new daemon)
    deleted_daemons = (ref_file_names).difference(cmp_file_names)
    deleted_config = get_daemons_config_names(deleted_daemons, ref_config_dict)

    # Case 2: A daemon is not present in "refrence" version but is
    # added/introduced in the "comparing" version
    # (A,B,C) cmp - (A,B) ref  = C (deleted daemon)
    new_daemons = cmp_file_names.difference(ref_file_names)
    new_config = get_daemons_config_names(new_daemons, config_dict)

    # Case 3: Compare the config options between the common daemons of
    # "reference" version and "comparing" version
    file_names = ref_file_names.intersection(cmp_file_names)
    for daemon in file_names:
        ref_daemon_configs = ref_config_dict[daemon]["options"]
        ref_daemon_config_names = set(
            map(lambda config_value: config_value["name"], ref_daemon_configs)
        )
        cmp_daemon_configs = config_dict[daemon]["options"]
        cmp_daemon_config_names = set(
            map(lambda config_value: config_value["name"], cmp_daemon_configs)
        )

        added = cmp_daemon_config_names.difference(ref_daemon_config_names)
        removed = ref_daemon_config_names.difference(cmp_daemon_config_names)

        new_config[daemon] = list(added)
        deleted_config[daemon] = list(removed)

        # get modified configs
        shared_config_names = ref_daemon_config_names.intersection(cmp_daemon_config_names)
        modified_config[daemon] = get_shared_config_daemon(
            shared_config_names, ref_daemon_configs, cmp_daemon_configs
        )

    # do not include daemons whose configurations have not changed
    new_config = {key: value for key, value in new_config.items() if len(value) != 0}
    deleted_config = {key: value for key, value in deleted_config.items() if len(value) != 0}
    modified_config = {key: value for key, value in modified_config.items() if len(value) != 0}

    final_result = defaultdict()
    final_result["added"] = new_config
    final_result["deleted"] = deleted_config
    final_result["modified"] = modified_config

    return final_result


def diff_branch(ref_repo: str, ref_branch: str, cmp_branch: str):
    sparse_branch_checkout(ref_repo, ref_branch, REF_CLONE_FOLDER, CEPH_CONFIG_OPTIONS_FOLDER_PATH)
    sparse_branch_checkout(ref_repo, cmp_branch, CMP_CLONE_FOLDER, CEPH_CONFIG_OPTIONS_FOLDER_PATH)

    final_result = diff_config()
    with open("diff_result.json", "w") as output_file:
        json.dump(final_result, output_file, indent=4)


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    subparsers = parser.add_subparsers(
        dest="mode", help="the mode in which diff should be performed"
    )

    # diff-branch mode
    parser_diff_branch = subparsers.add_parser("diff-branch", help="diff between branches")
    parser_diff_branch.add_argument(
        "--ref-repo",
        nargs="?",
        default=CEPH_UPSTREAM_REMOTE_URL,
        help="the repository URL from where the reference config files will be fetched",
    )
    parser_diff_branch.add_argument("--ref-branch", required=True, help="the reference branch")
    parser_diff_branch.add_argument(
        "--cmp-branch", required=True, help="the branch to compare against"
    )

    # diff-commit mode
    parser_diff_commit = subparsers.add_parser("diff-commit", help="diff between commits")
    parser_diff_commit.add_argument(
        "--ref-repo",
        nargs="?",
        default=CEPH_UPSTREAM_REMOTE_URL,
        help="the repository URL from where the reference config files will be fetched",
    )
    parser_diff_commit.add_argument("--ref-branch", required=True, help="the reference branch")
    parser_diff_commit.add_argument("--ref-sha", required=True, help="the reference commit SHA")
    parser_diff_commit.add_argument(
        "--cmp-sha", required=True, help="the commit SHA to compare against"
    )

    # diff-branch-remote-repo mode
    parser_diff_branch_remote_repo = subparsers.add_parser(
        "diff-branch-remote-repo", help="diff between branches in different repositories"
    )
    parser_diff_branch_remote_repo.add_argument(
        "--ref-repo",
        nargs="?",
        default=CEPH_UPSTREAM_REMOTE_URL,
        help="the repository URL from where the reference config files will be fetched",
    )
    parser_diff_branch_remote_repo.add_argument(
        "--remote-repo", required=True, help="the remote repository URL"
    )
    parser_diff_branch_remote_repo.add_argument(
        "--ref-branch", required=True, help="the reference branch"
    )
    parser_diff_branch_remote_repo.add_argument(
        "--cmp-branch", required=True, help="the branch to compare against"
    )

    args = parser.parse_args()

    if args.mode == "diff-branch":
        print(
            f"Running diff-branch with ref-repo: {args.ref_repo}, ref-branch: {args.ref_branch}, cmp-branch: {args.cmp_branch}"
        )
        diff_branch(args.ref_repo, args.ref_branch, args.cmp_branch)

    elif args.mode == "diff-commit":
        print(
            f"Running diff-commit with ref-repo: {args.ref_repo}, ref-branch: {args.ref_branch}, ref-sha: {args.ref_sha}, cmp-sha: {args.cmp_sha}"
        )
        # Add your logic for diff-commit mode here

    elif args.mode == "diff-branch-remote-repo":
        print(
            f"Running diff-branch-remote-repo with ref-repo: {args.ref_repo}, remote-repo: {args.remote_repo}, ref-branch: {args.ref_branch}, cmp-branch: {args.cmp_branch}"
        )
        # Add your logic for diff-branch-remote-repo mode here

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
