# Ceph Config Diff Tool

This program is a Python-based tool designed to compare the configuration options of Ceph by cloning the repository and analyzing the files present in the `src/common/options` directory. It supports three modes of operation: `diff-branch`, `diff-tag`, and `diff-branch-remote-repo`.

## Features

- **Compare Branches**: Compare configuration options between two branches in the same repository.
- **Compare Tags**: Compare configuration options between two tags in the same repository.
- **Compare Branches Across Repositories**: Compare configuration options between branches in different repositories.
- **Detailed Output**: Outputs added, deleted, and modified configuration options in JSON format.
- **Verbose Mode**: Prints detailed logs of commands being executed.

## Requirements

- Python 3.8 or higher
- Git installed on the system

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/your-username/ceph-config-diff.git
   cd ceph-config-diff
   ```

2. Install the required Python packages:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

Run the program using the following command:

```bash
python3 main.py <mode> [options]
```

### Modes

1. **`diff-branch`**: Compare configuration options between two branches in the same repository.
   ```bash
   python3 main.py diff-branch --ref-branch <branch1> --cmp-branch <branch2> [--ref-repo <repo-url>] [--verbose]
   ```

   - `--ref-branch`: The reference branch to compare against.
   - `--cmp-branch`: The branch to compare.
   - `--ref-repo`: (Optional) The repository URL. Defaults to the Ceph upstream repository.
   - `--verbose`: (Optional) Enable verbose mode.

2. **`diff-tag`**: Compare configuration options between two tags in the same repository.
   ```bash
   python3 main.py diff-tag --ref-tag <tag1> --cmp-tag <tag2> [--ref-repo <repo-url>] [--verbose]
   ```

   - `--ref-tag`: The reference tag to compare against.
   - `--cmp-tag`: The tag to compare.
   - `--ref-repo`: (Optional) The repository URL. Defaults to the Ceph upstream repository.
   - `--verbose`: (Optional) Enable verbose mode.

3. **`diff-branch-remote-repo`**: Compare configuration options between branches in different repositories.
   ```bash
   python3 main.py diff-branch-remote-repo --ref-branch <branch1> --cmp-branch <branch2> --remote-repo <repo-url> [--ref-repo <repo-url>] [--verbose]
   ```

   - `--ref-branch`: The reference branch to compare against.
   - `--cmp-branch`: The branch to compare.
   - `--remote-repo`: The remote repository URL for the branch to compare.
   - `--ref-repo`: (Optional) The repository URL for the reference branch. Defaults to the Ceph upstream repository.
   - `--verbose`: (Optional) Enable verbose mode.

### Example Commands

1. Compare two branches in the same repository:
   ```bash
   python3 main.py diff-branch --ref-branch main --cmp-branch feature-branch --verbose
   ```

2. Compare two tags in the same repository:
   ```bash
   python3 main.py diff-tag --ref-tag v1.0.0 --cmp-tag v1.1.0
   ```

3. Compare branches across repositories:
   ```bash
   python3 main.py diff-branch-remote-repo --ref-branch main --cmp-branch feature-branch --remote-repo https://github.com/username/ceph
   ```

## Output

The program generates a JSON file named diff_result.json containing the following structure:

```json
{
  "added": {
    "daemon1": ["config1", "config2"]
  },
  "deleted": {
    "daemon2": ["config3"]
  },
  "modified": {
    "daemon3": {
      "config4": {
        "key1": {
          "before": "old_value",
          "after": "new_value"
        }
      }
    }
  }
}
```

- **`added`**: Configuration options added in the comparing version.
- **`deleted`**: Configuration options removed in the comparing version.
- **`modified`**: Configuration options modified between the two versions.

## Error Handling

- Handles invalid branch/tag names and repository URLs.
- Provides meaningful error messages for missing files or directories.
- Ensures cleanup of temporary directories in case of errors.

## Contributing

Contributions are welcome! Please fork the repository and submit a pull request with your changes.

## License

This project is licensed under the MIT License. See the LICENSE file for details.

## Author

Developed by Naveen Naidu.

TEST
