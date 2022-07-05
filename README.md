# taichi-release-tests

This repo contains scripts for running examples in taichi main repo, DiffTaichi, QuanTaichi, and more.
This is part of the testing process to ensure real world applications behave as expected.


### How to run

1. Dependencies

The only dependency is `PyYAML`:

```
pip install PyYAML
```

2. Clone / symlink relevant repos to the `repos` directory

```
ln -sf /path/to/taichi repos/taichi
```

3. Run examples with configured timelines

```
# Run
python3 run.py --log=DEBUG timelines/

# Run 3 instances simultaneously
python3 run.py --log=DEBUG --runners 3 timelines/

# Regenerate captures
python3 run.py --log=DEBUG --generate-captures timelines/
```


### Conventions

1. One or multiple yaml file per example in `timelines` directory, but not one yaml file for multiple examples.
2. Put repos being tested in `repos` directory`
3. Put captures in `truths` directory. 
