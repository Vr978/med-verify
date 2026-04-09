// ─────────────────────────────────────────────────────────────────────────────
// MedVerify — Jenkins Declarative Pipeline
//
// Stages:
//   1. Checkout       — clone repo
//   2. Lint & Validate — check K8s manifests (kubectl dry-run)
//   3. Test           — run BatchValidator self-test
//   4. Build Images   — docker build for backend + fl_backend
//   5. Push to GCR    — push tagged images to Google Container Registry
//   6. Deploy to GKE  — kubectl apply all k8s/ manifests
//   7. Verify Rollout — wait for deployments to become ready
//
// Required Jenkins credentials (configure in Manage Jenkins > Credentials):
//   GCP_SA_KEY       — GCP service account JSON key (Secret File)
//   GCP_PROJECT_ID   — GCP project ID (Secret Text)
//   GKE_CLUSTER_NAME — GKE cluster name (Secret Text)
//   GKE_ZONE         — GKE cluster zone, e.g. us-central1-a (Secret Text)
// ─────────────────────────────────────────────────────────────────────────────

pipeline {
    agent any

    environment {
        // Image registry base — overridden by GCP_PROJECT_ID credential at runtime
        REGISTRY          = "gcr.io"
        IMAGE_BACKEND     = "${REGISTRY}/${GCP_PROJECT_ID}/medverify-backend"
        IMAGE_FL          = "${REGISTRY}/${GCP_PROJECT_ID}/medverify-fl-backend"
        IMAGE_TAG         = "${env.BUILD_NUMBER}-${env.GIT_COMMIT?.take(7) ?: 'local'}"
        KUBE_NAMESPACE    = "medverify"
    }

    options {
        timeout(time: 30, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '10'))
        disableConcurrentBuilds()           // prevent parallel deploys
        timestamps()
    }

    triggers {
        // Auto-trigger on push to main or any release/* branch
        githubPush()
    }

    stages {

        // ── Stage 1: Checkout ────────────────────────────────────────────────
        stage('Checkout') {
            steps {
                checkout scm
                echo "🔀 Branch: ${env.BRANCH_NAME} | Build: #${env.BUILD_NUMBER} | Commit: ${env.GIT_COMMIT?.take(7)}"
            }
        }

        // ── Stage 2: Lint & Validate Kubernetes Manifests ────────────────────
        stage('Lint & Validate') {
            steps {
                withCredentials([
                    file(credentialsId: 'GCP_SA_KEY', variable: 'GOOGLE_APPLICATION_CREDENTIALS'),
                    string(credentialsId: 'GCP_PROJECT_ID', variable: 'GCP_PROJECT_ID'),
                    string(credentialsId: 'GKE_CLUSTER_NAME', variable: 'GKE_CLUSTER_NAME'),
                    string(credentialsId: 'GKE_ZONE', variable: 'GKE_ZONE')
                ]) {
                    sh '''
                        echo "🔍 Authenticating with GCP..."
                        gcloud auth activate-service-account --key-file="$GOOGLE_APPLICATION_CREDENTIALS"
                        gcloud container clusters get-credentials "$GKE_CLUSTER_NAME" \
                            --zone "$GKE_ZONE" --project "$GCP_PROJECT_ID"

                        echo "📋 Dry-run validating Kubernetes manifests..."
                        kubectl apply --dry-run=client -f k8s/namespace.yaml
                        kubectl apply --dry-run=client -f k8s/configmap.yaml
                        kubectl apply --dry-run=client -f k8s/mongodb-deployment.yaml
                        kubectl apply --dry-run=client -f k8s/backend-deployment.yaml
                        kubectl apply --dry-run=client -f k8s/fl-backend-deployment.yaml
                        kubectl apply --dry-run=client -f k8s/hpa.yaml
                        echo "✅ All manifests valid."
                    '''
                }
            }
        }

        // ── Stage 3: Test — BatchValidator self-test ─────────────────────────
        stage('Test') {
            steps {
                sh '''
                    echo "🧪 Installing FL backend dependencies..."
                    python3 -m pip install --quiet --upgrade pip
                    python3 -m pip install --quiet -r fl_backend/requirements.txt

                    echo "🛡️ Running BatchValidator integrity self-test..."
                    python3 -m fl_backend.core.batch_validator

                    echo "✅ BatchValidator self-test passed."
                '''
            }
            post {
                failure {
                    echo "❌ BatchValidator self-test FAILED — blocking deploy."
                }
            }
        }

        // ── Stage 4: Build Docker Images ─────────────────────────────────────
        stage('Build Images') {
            parallel {
                stage('Build: DPoS Blockchain API') {
                    steps {
                        sh '''
                            echo "🐳 Building backend image..."
                            docker build \
                                --target runtime \
                                --tag "${IMAGE_BACKEND}:${IMAGE_TAG}" \
                                --tag "${IMAGE_BACKEND}:latest" \
                                ./backend
                            echo "✅ Backend image built: ${IMAGE_BACKEND}:${IMAGE_TAG}"
                        '''
                    }
                }
                stage('Build: FL Aggregator') {
                    steps {
                        sh '''
                            echo "🐳 Building fl-backend image..."
                            docker build \
                                --target runtime \
                                --tag "${IMAGE_FL}:${IMAGE_TAG}" \
                                --tag "${IMAGE_FL}:latest" \
                                ./fl_backend
                            echo "✅ FL backend image built: ${IMAGE_FL}:${IMAGE_TAG}"
                        '''
                    }
                }
            }
        }

        // ── Stage 5: Push to GCR ─────────────────────────────────────────────
        stage('Push to GCR') {
            when {
                // Only push on main branch or release tags
                anyOf {
                    branch 'main'
                    tag pattern: 'v\\d+\\.\\d+\\.\\d+', comparator: 'REGEXP'
                }
            }
            steps {
                withCredentials([file(credentialsId: 'GCP_SA_KEY', variable: 'GOOGLE_APPLICATION_CREDENTIALS')]) {
                    sh '''
                        echo "🔐 Authenticating Docker with GCR..."
                        gcloud auth configure-docker --quiet

                        echo "⬆️ Pushing backend images..."
                        docker push "${IMAGE_BACKEND}:${IMAGE_TAG}"
                        docker push "${IMAGE_BACKEND}:latest"

                        echo "⬆️ Pushing fl-backend images..."
                        docker push "${IMAGE_FL}:${IMAGE_TAG}"
                        docker push "${IMAGE_FL}:latest"

                        echo "✅ Images pushed to GCR."
                    '''
                }
            }
        }

        // ── Stage 6: Deploy to GKE ───────────────────────────────────────────
        stage('Deploy to GKE') {
            when {
                branch 'main'
            }
            steps {
                withCredentials([
                    file(credentialsId: 'GCP_SA_KEY', variable: 'GOOGLE_APPLICATION_CREDENTIALS'),
                    string(credentialsId: 'GCP_PROJECT_ID', variable: 'GCP_PROJECT_ID'),
                    string(credentialsId: 'GKE_CLUSTER_NAME', variable: 'GKE_CLUSTER_NAME'),
                    string(credentialsId: 'GKE_ZONE', variable: 'GKE_ZONE')
                ]) {
                    sh '''
                        echo "☸️ Deploying to GKE cluster: $GKE_CLUSTER_NAME"

                        # Patch image tags to the exact build so K8s triggers a rolling update
                        kubectl set image deployment/medverify-backend \
                            backend="${IMAGE_BACKEND}:${IMAGE_TAG}" \
                            -n "$KUBE_NAMESPACE" || \
                        kubectl apply -f k8s/backend-deployment.yaml -n "$KUBE_NAMESPACE"

                        kubectl set image deployment/medverify-fl-backend \
                            fl-backend="${IMAGE_FL}:${IMAGE_TAG}" \
                            -n "$KUBE_NAMESPACE" || \
                        kubectl apply -f k8s/fl-backend-deployment.yaml -n "$KUBE_NAMESPACE"

                        # Apply supporting resources (idempotent)
                        kubectl apply -f k8s/namespace.yaml
                        kubectl apply -f k8s/configmap.yaml
                        kubectl apply -f k8s/mongodb-deployment.yaml -n "$KUBE_NAMESPACE"
                        kubectl apply -f k8s/hpa.yaml -n "$KUBE_NAMESPACE"

                        echo "✅ Kubernetes resources applied."
                    '''
                }
            }
        }

        // ── Stage 7: Verify Rollout ──────────────────────────────────────────
        stage('Verify Rollout') {
            when {
                branch 'main'
            }
            steps {
                withCredentials([
                    file(credentialsId: 'GCP_SA_KEY', variable: 'GOOGLE_APPLICATION_CREDENTIALS'),
                    string(credentialsId: 'GKE_CLUSTER_NAME', variable: 'GKE_CLUSTER_NAME'),
                    string(credentialsId: 'GKE_ZONE', variable: 'GKE_ZONE'),
                    string(credentialsId: 'GCP_PROJECT_ID', variable: 'GCP_PROJECT_ID')
                ]) {
                    sh '''
                        echo "⏳ Waiting for rollout to complete..."

                        kubectl rollout status deployment/medverify-backend \
                            -n "$KUBE_NAMESPACE" --timeout=180s

                        kubectl rollout status deployment/medverify-fl-backend \
                            -n "$KUBE_NAMESPACE" --timeout=180s

                        echo ""
                        echo "📊 Pod status after deploy:"
                        kubectl get pods -n "$KUBE_NAMESPACE"

                        echo ""
                        echo "📈 HPA status:"
                        kubectl get hpa -n "$KUBE_NAMESPACE"

                        echo "✅ Rollout verified — MedVerify is live on GKE."
                    '''
                }
            }
        }
    }

    // ── Post-build notifications ─────────────────────────────────────────────
    post {
        success {
            echo "🎉 Pipeline SUCCESS — Build #${env.BUILD_NUMBER} deployed to GKE."
        }
        failure {
            echo "🚨 Pipeline FAILED — Build #${env.BUILD_NUMBER}. Check logs above."
        }
        always {
            // Clean up local Docker images to keep Jenkins agent disk healthy
            sh '''
                docker rmi "${IMAGE_BACKEND}:${IMAGE_TAG}" || true
                docker rmi "${IMAGE_FL}:${IMAGE_TAG}" || true
            '''
            cleanWs()
        }
    }
}
