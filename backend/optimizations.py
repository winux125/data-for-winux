"""Equivalent non-overlapping visual patch projection without tiny Conv3D kernels."""
def patch_projection(hidden_states, weight, bias):
    import torch.nn.functional as functional
    width = weight.shape[1] * weight.shape[2] * weight.shape[3] * weight.shape[4]
    return functional.linear(hidden_states.reshape(-1, width).to(weight.dtype),
                             weight.reshape(weight.shape[0], width), bias)


def optimize_visual_patch_embedding(model):
    from types import MethodType
    embed = model.model.visual.patch_embed
    def forward(self, hidden_states):
        return patch_projection(hidden_states, self.proj.weight, self.proj.bias)
    embed.forward = MethodType(forward, embed)
