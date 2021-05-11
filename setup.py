import setuptools


with open("README.md") as fp:
    long_description = fp.read()


setuptools.setup(
    name="benzaiten_aws_api_server",
    version="0.0.1",

    description="Benzaiten API Server for AWS",
    long_description=long_description,
    long_description_content_type="text/markdown",

    author="author",

    package_dir={"": "benzaiten_aws_api_server"},
    packages=setuptools.find_packages(where="benzaiten_aws_api_server"),

    install_requires=[
        "aws-cdk.core>=1.103.0",
        # "aws-cdk.aws-s3>=1.103.0",
        "aws-cdk.aws-lambda>=1.103.0",
        "aws-cdk.aws-kms>=1.103.0",
        "aws-cdk.aws-iam>=1.103.0",
        "aws-cdk.aws-dynamodb>=1.103.0",
        "aws-cdk.aws-apigateway>=1.103.0"
        "boto3>=1.17.70",
        "botocore>=1.20.70",
        "pycryptodome==3.10.1",
    ],

    python_requires=">=3.8",

    classifiers=[
        "Development Status :: 4 - Beta",

        "Intended Audience :: Developers",

        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.8",

        "Topic :: Software Development :: Code Generators",
        "Topic :: Utilities",

        "Typing :: Typed",
    ],
)
