output "ecr_repository_url" {
  value = aws_ecr_repository.app.repository_url
}

output "ecr_repository_name" {
  value = aws_ecr_repository.app.name
}

output "aws_account_id" {
  value = data.aws_caller_identity.current.account_id
}

output "aws_region" {
  value = var.aws_region
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "ecs_service_name" {
  value = aws_ecs_service.app.name
}

output "task_definition_family" {
  value = aws_ecs_task_definition.bootstrap.family
}

output "github_delivery_role_arn" {
  value = aws_iam_role.github_delivery.arn
}

output "task_execution_role_arn" {
  value = aws_iam_role.task_execution.arn
}

output "application_log_group" {
  value = aws_cloudwatch_log_group.app.name
}
