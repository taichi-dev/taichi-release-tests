import os
import yaml
import tempfile
import re
import pprint

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

def find_existing_examples(repo_name, github_addr, examples_dir, require_entrance=True):
    repo_dir = f"{tempdir}/{repo_name}/"
    os.system(f"git clone {github_addr} {repo_dir}")
    
    existing_examples = set()
    examples_root_dir = os.path.join(repo_dir, examples_dir)
    for path, _, files in os.walk(examples_root_dir):
        for filename in files:
            if not filename.endswith(".py"):
                continue

            filepath = os.path.join(path, filename)
            if require_entrance:
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

def find_untracked_release_tests(covered_release_test_names, existing_examples):
    untracked_tests = set()
    for test_name in existing_examples:
        if test_name in covered_release_test_names:
            continue
        untracked_tests.add(test_name)
    return untracked_tests

if __name__ == "__main__":
    root_dir = "timelines"
    covered_release_test_names = ci_covered_release_tests(root_dir)

    repo_name = "taichi"
    github_addr = "https://github.com/taichi-dev/taichi.git"
    examples_dir = f"python/taichi/examples"
    taichi_examples = find_existing_examples(repo_name, github_addr, examples_dir)

    repo_name = "difftaichi"
    github_addr = "https://github.com/taichi-dev/difftaichi.git"
    examples_dir = f""
    diff_examples = find_existing_examples(repo_name, github_addr, examples_dir)
    
    repo_name = "quantaichi"
    github_addr = "https://github.com/taichi-dev/quantaichi.git"
    examples_dir = f""
    quant_examples = find_existing_examples(repo_name, github_addr, examples_dir)

    untracked_tests = find_untracked_release_tests(covered_release_test_names, taichi_examples)
    untracked_tests = untracked_tests.union(find_untracked_release_tests(covered_release_test_names, diff_examples))
    untracked_tests = untracked_tests.union(find_untracked_release_tests(covered_release_test_names, quant_examples))
    print("Untracked Release Tests:")
    pp.pprint(untracked_tests)
