import pytest


def test_linear_projection_matches_nonoverlapping_conv3d():
    torch = pytest.importorskip('torch')
    from backend.optimizations import patch_projection
    torch.manual_seed(17)
    conv = torch.nn.Conv3d(3, 32, kernel_size=(2, 16, 16), stride=(2, 16, 16))
    patches = torch.randn(8, 3 * 2 * 16 * 16)
    actual = patch_projection(patches, conv.weight, conv.bias)
    expected = conv(patches.view(-1, 3, 2, 16, 16)).view(-1, 32)
    torch.testing.assert_close(actual, expected, atol=1e-6, rtol=1e-5)
