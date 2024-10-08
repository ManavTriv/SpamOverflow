# ----------------- MAIN ----------------- #
terraform {
    required_providers {
        aws = {
            source  = "hashicorp/aws"
            version = "~> 5.0"
        }
        docker = { 
            source = "kreuzwerker/docker" 
            version = "3.0.2" 
        }
    }
}

provider "aws" {
    region = "us-east-1"
    shared_credentials_files = ["./credentials"]
    default_tags {
        tags = {
            Course       = "CSSE6400"
            Name         = "SpamOverflow"
            Automation   = "Terraform"
        }
    }
}

locals { 
    image = "${aws_ecr_repository.spamoverflow.repository_url}:latest"
    database_username = "administrator" 
    database_password = "VerySecurePassword123XYZ" 
} 

data "aws_iam_role" "lab" {
    name = "LabRole"
}

data "aws_vpc" "default" {
    default = true
}

data "aws_subnets" "private" {
    filter {
        name   = "vpc-id"
        values = [data.aws_vpc.default.id]
    }
}

resource "local_file" "url" {
    content = "http://${aws_lb.spamoverflow.dns_name}/api/v1"
    filename = "./api.txt"
}

# ----------------- DOCKER IMAGE ----------------- #

data "aws_ecr_authorization_token" "ecr_token" {} 
 
provider "docker" { 
    registry_auth { 
        address = data.aws_ecr_authorization_token.ecr_token.proxy_endpoint 
        username = data.aws_ecr_authorization_token.ecr_token.user_name 
        password = data.aws_ecr_authorization_token.ecr_token.password 
    } 
}

resource "aws_ecr_repository" "spamoverflow" { 
    name = "spamoverflow" 
}

resource "docker_image" "spamoverflow" { 
    name = "${aws_ecr_repository.spamoverflow.repository_url}:latest" 
    build { 
        context = "." 
    } 
} 
 
resource "docker_registry_image" "spamoverflow" { 
    name = docker_image.spamoverflow.name 
}

# ----------------- DATABASE ----------------- #
 
resource "aws_db_instance" "database" {
    allocated_storage      = 20
    max_allocated_storage  = 1000
    engine                 = "postgres"
    engine_version         = "14"
    instance_class         = "db.t4g.micro"
    db_name                = "app"
    username               = local.database_username
    password               = local.database_password
    parameter_group_name   = "default.postgres14"
    skip_final_snapshot    = true
    vpc_security_group_ids = [aws_security_group.database.id]
    publicly_accessible    = true
}

resource "aws_security_group" "database" {
  name        = "app_database"
  description = "Allow inbound Postgres traffic"

  ingress {
    from_port        = 5432
    to_port          = 5432
    protocol         = "tcp"
    cidr_blocks      = ["0.0.0.0/0"]
  }

  egress {
    from_port        = 0
    to_port          = 0
    protocol         = "-1"
    cidr_blocks      = ["0.0.0.0/0"]
    ipv6_cidr_blocks = ["::/0"]
  }
}

# ----------------- ECS ----------------- #

resource "aws_ecs_cluster" "spamoverflow" {
    name = "spamoverflow"
}

resource "aws_ecs_task_definition" "app" {
  family                   = "app"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = 1024
  memory                   = 2048
  execution_role_arn       = data.aws_iam_role.lab.arn

  container_definitions = <<DEFINITION
[
  {
    "image": "${local.image}",
    "cpu": 1024,
    "memory": 2048,
    "name": "app",
    "networkMode": "awsvpc",
    "portMappings": [
      {
        "containerPort": 8080,
        "hostPort": 8080
      }
    ],
    "environment": [
      {
        "name": "SQLALCHEMY_DATABASE_URI",
        "value": "postgresql://${local.database_username}:${local.database_password}@${aws_db_instance.database.address}:${aws_db_instance.database.port}/${aws_db_instance.database.db_name}"
      }
    ],
    "logConfiguration": {
      "logDriver": "awslogs",
      "options": {
        "awslogs-group": "/spamoverflow/app",
        "awslogs-region": "us-east-1",
        "awslogs-stream-prefix": "ecs",
        "awslogs-create-group": "true"
      }
    }
  }
]
DEFINITION
}


resource "aws_ecs_service" "spamoverflow" {
    name            = "spamoverflow"
    cluster         = aws_ecs_cluster.spamoverflow.id
    task_definition = aws_ecs_task_definition.app.arn
    desired_count   = 1
    launch_type     = "FARGATE"

    network_configuration {
        subnets             = data.aws_subnets.private.ids
        security_groups     = [aws_security_group.app.id]
        assign_public_ip    = true
    }

    load_balancer { 
        target_group_arn = aws_lb_target_group.app.arn 
        container_name   = "app" 
        container_port   = 8080 
    }

}

resource "aws_security_group" "app" {
    name = "app"
    description = "SpamOverflow Security Group"

    ingress {
        from_port = 8080
        to_port = 8080
        protocol = "tcp"
        cidr_blocks = ["0.0.0.0/0"]
    }

    ingress {
        from_port = 22
        to_port = 22
        protocol = "tcp"
        cidr_blocks = ["0.0.0.0/0"]
    }

    egress {
        from_port = 0
        to_port = 0
        protocol = "-1"
        cidr_blocks = ["0.0.0.0/0"]
    }
}

# ----------------- LOAD BALANCERS ----------------- #

resource "aws_lb_target_group" "app" { 
    name          = "app" 
    port          = 8080 
    protocol      = "HTTP" 
    vpc_id        = aws_security_group.app.vpc_id 
    target_type   = "ip" 
    
    health_check { 
        path                = "/api/v1/health" 
        port                = "8080" 
        protocol            = "HTTP" 
        healthy_threshold   = 2 
        unhealthy_threshold = 2 
        timeout             = 5 
        interval            = 10 
  } 
}

resource "aws_lb" "spamoverflow" { 
    name               = "spamoverflow" 
    internal           = false 
    load_balancer_type = "application" 
    subnets            = data.aws_subnets.private.ids 
    security_groups    = [aws_security_group.spamoverflow.id] 
} 
 
resource "aws_security_group" "spamoverflow" { 
    name        = "spamoverflow" 
    description = "SpamOverflow Security Group" 
    
    ingress { 
        from_port     = 80 
        to_port       = 80 
        protocol      = "tcp" 
        cidr_blocks   = ["0.0.0.0/0"] 
    } 
    
    egress { 
        from_port     = 0 
        to_port       = 0 
        protocol      = "-1" 
        cidr_blocks   = ["0.0.0.0/0"] 
    } 
}

resource "aws_lb_listener" "app" { 
    load_balancer_arn   = aws_lb.spamoverflow.arn 
    port                = "80" 
    protocol            = "HTTP" 
    
    default_action { 
        type              = "forward" 
        target_group_arn  = aws_lb_target_group.app.arn 
    } 
}

# ----------------- AUTOSCALING ----------------- #

resource "aws_appautoscaling_target" "app" { 
    max_capacity        = 4 
    min_capacity        = 1 
    resource_id         = "service/spamoverflow/spamoverflow" 
    scalable_dimension  = "ecs:service:DesiredCount" 
    service_namespace   = "ecs" 
    
    depends_on = [ aws_ecs_service.spamoverflow ] 
} 
 
 
resource "aws_appautoscaling_policy" "app-cpu" { 
    name                = "app-cpu" 
    policy_type         = "TargetTrackingScaling" 
    resource_id         = aws_appautoscaling_target.app.resource_id 
    scalable_dimension  = aws_appautoscaling_target.app.scalable_dimension 
    service_namespace   = aws_appautoscaling_target.app.service_namespace 
    
    target_tracking_scaling_policy_configuration { 
        predefined_metric_specification { 
        predefined_metric_type  = "ECSServiceAverageCPUUtilization" 
        } 
    
        target_value              = 20 
    } 
}

# ----------------- QUEUE ----------------- #

resource "aws_sqs_queue" "scan_queue" { 
   name = "scan" 
}
