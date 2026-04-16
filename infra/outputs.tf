output "ecr_repository_url" {
  value = aws_ecr_repository.main.repository_url
}

output "alb_dns_name" {
  value = aws_lb.main.dns_name
}

output "s3_bucket_name" {
  value = aws_s3_bucket.main.bucket
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.main.name
}
