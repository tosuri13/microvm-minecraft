import aws_cdk as cdk
from aws_cdk import aws_iam as iam
from aws_cdk import aws_s3_assets as s3_assets
from constructs import Construct


class MicrovmMinecraftStack(cdk.Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        region = self.region

        microvm_minecraft_code_artifact = s3_assets.Asset(
            self,
            "MicrovmMinecraftCodeArtifact",
            path="../artifact",
        )

        microvm_minecraft_build_role = iam.CfnRole(
            self,
            "MicrovmMinecraftBuildRole",
            assume_role_policy_document={
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"Service": "lambda.amazonaws.com"},
                        "Action": ["sts:AssumeRole", "sts:TagSession"],
                    }
                ],
            },
            policies=[
                iam.CfnRole.PolicyProperty(
                    policy_name="microvm-minecraft-build-policy",
                    policy_document={
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Action": [
                                    "logs:CreateLogGroup",
                                    "logs:CreateLogStream",
                                    "logs:PutLogEvents",
                                    "s3:GetObject",
                                    "s3:GetBucketLocation",
                                ],
                                "Resource": "*",
                            }
                        ],
                    },
                )
            ],
            role_name="microvm-minecraft-build-role",
        )

        cdk.CfnResource(
            self,
            "MicrovmMinecraftMicrovmImage",
            type="AWS::Lambda::MicrovmImage",
            properties={
                "Name": "microvm-minecraft-microvm-image",
                "Description": "Minecraft Server on Lambda MicroVMs",
                "BaseImageArn": f"arn:aws:lambda:{region}:aws:microvm-image:al2023-1",
                "BaseImageVersion": "0",
                "BuildRoleArn": microvm_minecraft_build_role.attr_arn,
                "CodeArtifact": {
                    "Uri": microvm_minecraft_code_artifact.s3_object_url,
                },
                "CpuConfigurations": [{"Architecture": "ARM_64"}],
                "Resources": [{"MinimumMemoryInMiB": 4096}],
                "AdditionalOsCapabilities": ["ALL"],
                "EgressNetworkConnectors": [
                    f"arn:aws:lambda:{region}:aws:network-connector:aws-network-connector:INTERNET_EGRESS",
                ],
                "EnvironmentVariables": [],
                "Hooks": {
                    "Port": 9000,
                    "MicrovmImageHooks": {
                        "Ready": "ENABLED",
                        "ReadyTimeoutInSeconds": 300,
                    },
                    "MicrovmHooks": {
                        "Run": "ENABLED",
                        "RunTimeoutInSeconds": 60,
                        "Suspend": "ENABLED",
                        "SuspendTimeoutInSeconds": 30,
                        "Terminate": "ENABLED",
                        "TerminateTimeoutInSeconds": 30,
                    },
                },
                "Logging": {"Disabled": False},
            },
        )
