import aws_cdk as cdk
from stack import MicrovmMinecraftStack

app = cdk.App()

MicrovmMinecraftStack(app, "microvm-minecraft-app")

app.synth()
