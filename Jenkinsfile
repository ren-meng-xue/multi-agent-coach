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
          JENKINS_UID="$(id -u)"
          JENKINS_GID="$(id -g)"
          docker run --rm -u 0:0 -v "$DEPLOY_DIR:/deploy" alpine:3.20 sh -eu -c "
            chown -R ${JENKINS_UID}:${JENKINS_GID} /deploy
            chmod -R u+rwX /deploy
          "
          test -d "$DEPLOY_DIR/.git"
          test -f "$DEPLOY_DIR/.env.deploy"
        '''
      }
    }

    stage('Update Source') {
      steps {
        sh '''
          set -eu
          cd "$DEPLOY_DIR"
          for attempt in 1 2 3 4 5; do
            if git fetch origin "$DEPLOY_BRANCH" &&
               git checkout "$DEPLOY_BRANCH" &&
               git pull --ff-only origin "$DEPLOY_BRANCH"; then
              break
            fi
            if [ "$attempt" = 5 ]; then
              exit 1
            fi
            sleep $((attempt * 10))
          done
        '''
      }
    }

    stage('Build And Deploy') {
      steps {
        sh '''
          set -eu
          cd "$DEPLOY_DIR"
          docker compose up -d --build
        '''
      }
    }

    stage('Verify') {
      steps {
        sh '''
          set -eu
          cd "$DEPLOY_DIR"
          trap 'docker compose ps; docker compose logs --tail=120 frontend' EXIT
          docker compose ps
          curl --max-time 10 -fsS http://localhost:8000/api/v1/health
          for attempt in 1 2 3 4 5 6 7 8 9 10 11 12; do
            if curl --max-time 10 -fsS http://localhost:3000/healthz >/dev/null; then
              break
            fi
            if [ "$attempt" = 12 ]; then
              exit 1
            fi
            sleep 5
          done
        '''
      }
    }
  }
}
