terraform {
    required_providers {
        aws = {
            source  = "hashicorp/aws"
            version = "~> 4.0"
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
    database_password = "password" # this is bad 
} 
 
resource "aws_db_instance" "database" { 
    allocated_storage = 20 
    max_allocated_storage = 1000 
    engine = "postgres" 
    engine_version = "14" 
    instance_class = "db.t4g.micro" 
    db_name = "spamoverflow" 
    username = local.database_username 
    password = local.database_password 
    parameter_group_name = "default.postgres14" 
    skip_final_snapshot = true 
    vpc_security_group_ids = [aws_security_group.spamoverflow_database.id] 
    publicly_accessible = true 
 
    tags = { 
        Name = "spamoverflow_database" 
    } 
}

resource "aws_security_group" "spamoverflow_database" { 
    name = "spamoverflow_database" 
    description = "Allow inbound Postgresql traffic" 
    
    ingress { 
        from_port = 5432 
        to_port = 5432 
        protocol = "tcp" 
        cidr_blocks = ["0.0.0.0/0"] 
    } 
    
    egress { 
        from_port = 0 
        to_port = 0 
        protocol = "-1" 
        cidr_blocks = ["0.0.0.0/0"] 
        ipv6_cidr_blocks = ["::/0"] 
    } 
    
    tags = { 
        Name = "spamoverflow_database" 
    } 
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

resource "aws_ecs_cluster" "spamoverflow" { 
    name = "spamoverflow" 
}

resource "aws_ecs_task_definition" "spamoverflow" {
    family                   = "spamoverflow"
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
    "name": "todo",
    "networkMode": "awsvpc",
    "portMappings": [
      {
        "containerPort": 6400,
        "hostPort": 6400
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
        "awslogs-group": "/spamoverflow/spamoverflow",
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
    name = "spamoverflow" 
    cluster = aws_ecs_cluster.spamoverflow.id 
    task_definition = aws_ecs_task_definition.spamoverflow.arn 
    desired_count = 1 
    launch_type = "FARGATE" 
    
    network_configuration { 
            subnets = data.aws_subnets.private.ids 
            security_groups = [aws_security_group.spamoverflow.id] 
            assign_public_ip = true 
    } 
}

resource "aws_security_group" "spamoverflow" { 
    name = "spamoverflow" 
    description = "SpamOverflow Security Group" 
    
    ingress { 
        from_port = 6400 
        to_port = 6400 
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

resource "local_file" "url" {
    content = "${aws_db_instance.database.address}/api/v1"
    filename = "./api.txt"
}