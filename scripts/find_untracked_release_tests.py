import os
import yaml
import tempfile
import re
import pprint
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("-c", "--check_for_main", default=False, help="Only python files with \"if __name__ == \"__main__\"\" are counted into Demo files",
                    action="store_true")
args = parser.parse_args()

pp = pprint.PrettyPrinter(indent=4)
tempdir = tempfile.mkdtemp()

def ci_covered_release_tests(root_dir, pre_fix="repos/"):
    covered_release_test_names = set()
    for path, _, files in os.walk(root_dir):
        for filename in files:
            filepath = os.path.join(path, filename)
            with open(filepath, "r") as f:
                content = yaml.safe_load(f)

            for item in content:
                if "path" in item.keys():
                    test_path = item["path"]
                    
                    # Remove pre-fix
                    if test_path.startswith(pre_fix):
                        test_path = test_path[len(pre_fix):]
                        covered_release_test_names.add(test_path)

    return covered_release_test_names


def find_existing_examples(repo_name, github_addr, examples_dir, check_for_main):
    repo_dir = f"{tempdir}/{repo_name}/"
    try:
        os.system(f"git clone {github_addr} {repo_dir} --depth=1")
    except Exception as e:
        print("Unable to git clone {repo_name} from {github_addr}")
        raise e.what()

    existing_examples = set()
    examples_root_dir = os.path.join(repo_dir, examples_dir)
    for path, _, files in os.walk(examples_root_dir):
        for filename in files:
            if not filename.endswith(".py"):
                continue

            filepath = os.path.join(path, filename)
            if check_for_main:
                with open(filepath, "r") as f:
                    fcontent = f.read()
                    pattern = r"if __name__\s*==\s*[\\\'\\\"]__main__[\\\'\\\"]\s*:"
                    m = re.search(pattern, fcontent)
                    if m is None:
                        continue

            rel_path = path
            if path.startswith(repo_dir):
                rel_path = path[len(repo_dir):]
            
            full_path = os.path.join(repo_name, rel_path, filename)
            existing_examples.add(f"{full_path}")
    return existing_examples


def main():
    root_dir = "timelines"
    covered_release_test_names = ci_covered_release_tests(root_dir)

    test_info = {
        "taichi" : ["https://github.com/taichi-dev/taichi.git", "python/taichi/examples"],
        "difftaichi" : ["https://github.com/taichi-dev/difftaichi.git", ""],
        "quantaichi" : ["https://github.com/taichi-dev/quantaichi.git", ""]
    }

    existing_examples = set()
    for repo_name, (github_addr, examples_dir) in test_info.items():
        existing_examples |= find_existing_examples(repo_name, github_addr, examples_dir, args.check_for_main)
    
    untracked_tests = existing_examples - covered_release_test_names
    
    print("Untracked Release Tests:")
    pp.pprint(untracked_tests)



if __name__ == "__main__":
    main()
