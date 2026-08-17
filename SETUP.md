## Infrastructure and deployment setup

The Delivery workflow starts after Testing github action workflow succeeds on a git push.

### Configure HCP Terraform state

Set the HCP Terraform workspace execution mode to Local (custom). Terraform commands then run on the GitHub-hosted runner, while HCP Terraform stores and synchronizes the state.

![HCP Terraform workspace set to local execution mode](images/hcp-terraform-local-execution-mode.png)

Create API token to bind it to github actions

![Creating a short-lived HCP Terraform team token](images/hcp-terraform-team-token-creation.png)

Put the token inside github secret

![HCP Terraform token initially stored under the Main environment](images/github-main-environment-hcp-token-secret.png)


| Name | Type | Required value |
| --- | --- | --- |
| HCP_TERRAFORM_TOKEN | Secret | The HCP Terraform team token |
| HCP_TERRAFORM_ORGANIZATION | Variable | The exact HCP Terraform organization name |
| HCP_TERRAFORM_WORKSPACE | Variable | The exact HCP Terraform workspace name |
| AWS_TERRAFORM_ROLE_ARN | Variable | The ARN of the bootstrap IAM role, in the form `arn:aws:iam::<ACCOUNT_ID>:role/<ROLE_NAME>` |
| AWS_DELIVERY_OIDC_SUBJECT | Variable | The exact GitHub OIDC claim for the environment, without a wildcard |

![GitHub infrastructure environment secret and variables](images/github-infrastructure-environment-variables.png)

### Create the AWS OIDC provider for Github Deployment

![AWS IAM Identity providers menu](images/aws-iam-identity-providers-menu.png)

| Field | Value |
| --- | --- |
| Provider URL | `https://token.actions.githubusercontent.com` |
| Audience | `sts.amazonaws.com` |

![AWS IAM GitHub OIDC provider configuration](images/aws-iam-github-oidc-provider-configuration.png)

### Create the Terraform deployment role

![AWS IAM custom trust policy for the GitHub OIDC role](images/aws-iam-github-oidc-role-trust-policy.png)

![AWS IAM inline policy editor for the Terraform role](images/aws-iam-terraform-role-inline-policy.png)

![AWS IAM role review before creation](images/aws-iam-github-oidc-role-review.png)

![AWS IAM summary of the Terraform role permissions](images/aws-iam-github-oidc-role-permissions-summary.png)

### Correct the role ARN before running the workflow

`AWS_TERRAFORM_ROLE_ARN` must contain the IAM role ARN. The captured value below ends with `oidc-provider/token.actions.githubusercontent.com`, so it is the provider ARN and cannot be passed to `role-to-assume`.

![OIDC provider ARN entered in the AWS Terraform role ARN variable](images/github-aws-terraform-role-arn-variable.png)

Use a value with this shape instead:

```text
arn:aws:iam::<ACCOUNT_ID>:role/GithubActionOIDC_Deploy
```