from cstation.models import GitHubRepoConfig


def test_github_repo_config_coerces_float_branch():
    config = GitHubRepoConfig(
        name="test_repo",
        branch=18.0,
        local_path="/opt/PW/test",
    )
    assert config.branch == "18.0"


def test_github_repo_config_coerces_int_branch():
    config = GitHubRepoConfig(
        name="test_repo",
        branch=18,
        local_path="/opt/PW/test",
    )
    assert config.branch == "18"
