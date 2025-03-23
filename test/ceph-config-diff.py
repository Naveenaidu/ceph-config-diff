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

#!/usr/bin/env python3

import yaml
import argparse
import subprocess
import glob
import math
import os
import sys
import json
import re

from collections import defaultdict

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
def sparse_branch_checkout(repo_url: str, branch_name: str, clone_folder_name: str, config_options_path: str):
    commands = [
        f"rm -rf {clone_folder_name}",
        f"git clone --filter=blob:none --no-checkout --depth 1 --single-branch --branch {branch_name} --sparse {repo_url} {clone_folder_name}",
        f"git sparse-checkout add {config_options_path}",
        "git checkout"
    ]
    
    # Run the first 2 commands in current directory
    for command in commands[0:2]:
        print(command)
        result = subprocess.run(command, shell=True, check=True, text=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        if result.returncode != 0:
            print(f"Command failed: {command}")
            sys.exit(result.returncode)
    
    # Run the sparse checkout in cloned directory
    for command in commands[2:]:
        print(command)
        result = subprocess.run(command, shell=True, check=True, text=True, cwd=clone_folder_name, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        if result.returncode != 0:
            print(f"Command failed: {command}")
            sys.exit(result.returncode)


def load_config_yaml_files(path: str):
    files = glob.glob(f"{path}/*.yaml.in")
    file_names = map(lambda filepath: os.path.basename(filepath), files)

    config_options = defaultdict()

    for file in files:
        with open(file, 'r') as stream:
            try:
                
                # Preprocess the file to enclose template value in double quotes
                # eg: @CEPH_INSTALL_FULL_PKGLIBDIR@/erasure-code -> "@CEPH_INSTALL_FULL_PKGLIBDIR@/erasure-code"
                # This pre-process is okay since these values are dependent on the build system and as such
                # cannot be found out until the entire ceph is built - which is a cumbersome process

                file_content = stream.read()
                # Enclose @key@somemoretext in double quotes
                file_content = re.sub(r'@.*@.*', r'"\g<0>"', file_content)

                file_name = os.path.basename(file)
                file_config_options = yaml.safe_load(file_content)
                config_options[file_name] = file_config_options

            except yaml.YAMLError as excep:
                print(excep)
    
    return set(file_names), config_options

def diff_config():
    ref_file_names, ref_config_dict = load_config_yaml_files(f"{REF_CLONE_FOLDER}/{CEPH_CONFIG_OPTIONS_FOLDER_PATH}")
    cmp_file_names, config_dict = load_config_yaml_files(f"{CMP_CLONE_FOLDER}/{CEPH_CONFIG_OPTIONS_FOLDER_PATH}")

    new_config = defaultdict()
    deleted_config = defaultdict()
    modified_config = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))

    # Case: Where entire new daemon configuration is added
    # (A,B,C) ref - (A,B) cmp == C (new daemon)
    new_daemons = (ref_file_names).difference(cmp_file_names)
    for daemon in new_daemons:
        new_daemon_configs_list = ref_config_dict[daemon]['options']
        new_daemon_configs_keys = set(map(lambda config_value: config_value['name'], new_daemon_configs_list))
        new_config[daemon] = list(new_daemon_configs_keys)
    
    # Case: Where entire deamon config is deleted
    # (A,B,C) cmp - (A,B) ref  = C (deleted daemon)
    deleted_daemons = cmp_file_names.difference(ref_file_names)
    for daemon in deleted_daemons:
        deleted_daemon_configs_list = config_dict[daemon]['options']
        deleted_daemon_configs_keys = set(map(lambda config_value: config_value['name'], deleted_daemon_configs_list))
        deleted_config[daemon] = list(deleted_daemon_configs_keys)


    # Shared config files
    file_names = cmp_file_names.intersection(ref_file_names)
    print(file_names)
    for daemon in file_names:
        ref_daemon_configs_list = ref_config_dict[daemon]['options']
        cmp_daemon_configs_list = config_dict[daemon]['options']

        ref_daemon_configs_keys = set(map(lambda config_value: config_value['name'], ref_daemon_configs_list))
        cmp_daemon_configs_keys = set(map(lambda config_value: config_value['name'], cmp_daemon_configs_list))
        
        removed = cmp_daemon_configs_keys - ref_daemon_configs_keys
        added = ref_daemon_configs_keys - cmp_daemon_configs_keys
        new_config[daemon] = list(added)
        deleted_config[daemon] = list(removed)
        
        # get modified configs
        shared_configs = ref_daemon_configs_keys.intersection(cmp_daemon_configs_keys)
        """
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
        for config_name in shared_configs:
            ref_daemon_config = defaultdict()
            cmp_deamon_config = defaultdict()

            ref_daemon_config = next(filter(lambda deamon_config: deamon_config['name'] == config_name, ref_daemon_configs_list), None)
            cmp_deamon_config = next(filter(lambda deamon_config: deamon_config['name'] == config_name, cmp_daemon_configs_list), None)
            ref_daemon_config_keys = set(ref_daemon_config.keys())
            cmp_deamon_config_keys = set(cmp_deamon_config.keys())

            # Check if a key was added or deleted for a particular config, if it is replace either "before" are "after" with empty quotes (Do we want to add soemthing like <ADDED> or <DELETED>??)
            new_config_keys = ref_daemon_config_keys.difference(cmp_deamon_config_keys)
            deleted_config_keys = cmp_deamon_config_keys.difference(ref_daemon_config_keys)

            for config_key in new_config_keys:
                modified_config[daemon][config_name][config_key]["before"] = ""
                modified_config[daemon][config_name][config_key]["after"] = ref_daemon_config[config_key]
            
            for config_key in deleted_config_keys:
                modified_config[daemon][config_name][config_key]["before"] = cmp_deamon_config[config_key]
                modified_config[daemon][config_name][config_key]["after"] = ""
            
            shared_config_keys = ref_daemon_config_keys.intersection(cmp_deamon_config_keys)
            for config_key in shared_config_keys:
                if ref_daemon_config[config_key] != cmp_deamon_config[config_key]:
                    modified_config[daemon][config_name][config_key]["before"] = cmp_deamon_config[config_key]
                    modified_config[daemon][config_name][config_key]["after"] = ref_daemon_config[config_key]

    
    """
    remove all configs where no change occured
    """
    new_config_filtered = {key : value for key, value in new_config.items() if len(value) != 0}
    deleted_config_filtered = {key : value for key, value in deleted_config.items() if len(value) != 0}
    modified_config_filtered = {key : value for key, value in modified_config.items() if len(value) != 0}

    final_result = defaultdict()
    final_result['added'] = new_config_filtered
    final_result['deleted'] = deleted_config_filtered
    final_result['modified'] = modified_config_filtered

    print(json.dumps(final_result))

def diff_branch(ref_repo: str, ref_branch: str, cmp_branch: str):
    # sparse_branch_checkout(ref_repo, ref_branch, REF_CLONE_FOLDER, CEPH_CONFIG_OPTIONS_FOLDER_PATH)
    # sparse_branch_checkout(ref_repo, cmp_branch, CMP_CLONE_FOLDER, CEPH_CONFIG_OPTIONS_FOLDER_PATH)

    diff_config()

def main():
    ceph_upstream_repo_url = "https://github.com/ceph/ceph.git"

    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    subparsers = parser.add_subparsers(dest='mode', help='the mode in which diff should be performed')

    # diff-branch mode
    parser_diff_branch = subparsers.add_parser('diff-branch', help='diff between branches')
    parser_diff_branch.add_argument('--ref-repo', nargs='?', default=CEPH_UPSTREAM_REMOTE_URL,
                                    help='the repository URL from where the reference config files will be fetched')
    parser_diff_branch.add_argument('--ref-branch', required=True, help='the reference branch')
    parser_diff_branch.add_argument('--cmp-branch', required=True, help='the branch to compare against')

    # diff-commit mode
    parser_diff_commit = subparsers.add_parser('diff-commit', help='diff between commits')
    parser_diff_commit.add_argument('--ref-repo', nargs='?', default=CEPH_UPSTREAM_REMOTE_URL,
                                    help='the repository URL from where the reference config files will be fetched')
    parser_diff_commit.add_argument('--ref-branch', required=True, help='the reference branch')
    parser_diff_commit.add_argument('--ref-sha', required=True, help='the reference commit SHA')
    parser_diff_commit.add_argument('--cmp-sha', required=True, help='the commit SHA to compare against')

    # diff-branch-remote-repo mode
    parser_diff_branch_remote_repo = subparsers.add_parser('diff-branch-remote-repo', help='diff between branches in different repositories')
    parser_diff_branch_remote_repo.add_argument('--ref-repo', nargs='?', default=CEPH_UPSTREAM_REMOTE_URL,
                                                help='the repository URL from where the reference config files will be fetched')
    parser_diff_branch_remote_repo.add_argument('--remote-repo', required=True, help='the remote repository URL')
    parser_diff_branch_remote_repo.add_argument('--ref-branch', required=True, help='the reference branch')
    parser_diff_branch_remote_repo.add_argument('--cmp-branch', required=True, help='the branch to compare against')

    args = parser.parse_args()

    if args.mode == 'diff-branch':
        print(f"Running diff-branch with ref-repo: {args.ref_repo}, ref-branch: {args.ref_branch}, cmp-branch: {args.cmp_branch}")
        diff_branch(args.ref_repo, args.ref_branch, args.cmp_branch)

    elif args.mode == 'diff-commit':
        print(f"Running diff-commit with ref-repo: {args.ref_repo}, ref-branch: {args.ref_branch}, ref-sha: {args.ref_sha}, cmp-sha: {args.cmp_sha}")
        # Add your logic for diff-commit mode here

    elif args.mode == 'diff-branch-remote-repo':
        print(f"Running diff-branch-remote-repo with ref-repo: {args.ref_repo}, remote-repo: {args.remote_repo}, ref-branch: {args.ref_branch}, cmp-branch: {args.cmp_branch}")
        # Add your logic for diff-branch-remote-repo mode here

    else:
        parser.print_help()

if __name__ == '__main__':
    main()
