import torch
import torch.nn as nn

class UNet(nn.Module):
    def __init__(self, in_channels=2, out_channels=1, init_features=32, depth=4):
        super().__init__()
        features = init_features
        self.encoders = nn.ModuleList()
        self.pools = nn.ModuleList()
        for i in range(depth):
            self.encoders.append(UNet._block(in_channels, features))
            self.pools.append(nn.MaxPool2d(kernel_size=2, stride=2))
            in_channels = features
            features *= 2
        self.encoders.append(UNet._block(in_channels, features))

        self.upconvs = nn.ModuleList()
        self.decoders = nn.ModuleList()
        for i in range(depth):
            self.upconvs.append(nn.ConvTranspose2d(features, features // 2, kernel_size=2, stride=2))
            self.decoders.append(UNet._block(features, features//2))
            features = features // 2

        self.conv = nn.Conv2d(in_channels=features, out_channels=out_channels, kernel_size=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        encodings = []
        for encoder, pool in zip(self.encoders, self.pools):
            x = encoder(x)
            encodings.append(x)
            x = pool(x)
        x = self.encoders[-1](x)

        for upconv, decoder, encoding in zip(self.upconvs, self.decoders, reversed(encodings)):
            x = upconv(x)
            x = torch.cat((x, encoding), dim=1)
            x = decoder(x)

        return self.conv(x)

    @staticmethod
    def _block(in_channels, features):
        return nn.Sequential(
            nn.Conv2d(
                in_channels=in_channels,
                out_channels=features,
                kernel_size=5,
                padding="same",
                bias=True,
            ),
            nn.BatchNorm2d(num_features=features),
            nn.ReLU(inplace=True),      
            nn.Conv2d(
                in_channels=features,
                out_channels=features,
                kernel_size=5,
                padding="same",
                bias=True,
            ),        
            nn.ReLU(inplace=True),
        )

def weights_init(m):
    classname = m.__class__.__name__
    if classname.find("Conv") != -1:
        m.weight.data.normal_(0.0, 0.02)
    elif classname.find("BatchNorm") != -1:
        m.weight.data.normal_(1.0, 0.02)
        m.bias.data.zero_()