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
        "aws-cdk.core==1.100.0",
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
