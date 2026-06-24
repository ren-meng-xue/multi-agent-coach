pipeline {
  agent any

  options {
    timestamps()
    disableConcurrentBuilds()
  }

  environment {
    DEPLOY_DIR = '/www/wwwroot/multi-agent-coach'
    DEPLOY_BRANCH = 'main'
    COMPOSE_PROJECT_NAME = 'multi-agent-coach'
  }

  stages {
    stage('Preflight') {
      steps {
        sh '''
          set -eu
          docker --version
          docker compose version
          test -d "$DEPLOY_DIR/.git"
          test -f "$DEPLOY_DIR/.env.deploy"
        '''
      }
    }

    stage('Update Source') {
      steps {
        dir("${DEPLOY_DIR}") {
          sh '''
            set -eu
            git fetch origin "$DEPLOY_BRANCH"
            git checkout "$DEPLOY_BRANCH"
            git pull --ff-only origin "$DEPLOY_BRANCH"
          '''
        }
      }
    }

    stage('Build And Deploy') {
      steps {
        dir("${DEPLOY_DIR}") {
          sh '''
            set -eu
            docker compose up -d --build
          '''
        }
      }
    }

    stage('Verify') {
      steps {
        dir("${DEPLOY_DIR}") {
          sh '''
            set -eu
            docker compose ps
            curl -fsS http://localhost:8000/api/v1/health
            curl -fsS http://localhost:3000 >/dev/null
          '''
        }
      }
    }
  }
}
