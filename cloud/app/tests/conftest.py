"""Test fixtures."""

import pytest


@pytest.fixture
def test_keypair():
    """Generate a fresh keypair for each test."""
    from cloud.app.core.security import generate_keypair
    return generate_keypair()
