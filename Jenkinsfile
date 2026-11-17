pipeline {
    agent any

    options {
        timestamps()
        disableConcurrentBuilds()
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Python Environment Setup') {
            steps {
                bat '''
                    python --version
                    if not exist .venv\\Scripts\\python.exe (
                        python -m venv .venv
                    )
                    .venv\\Scripts\\python.exe --version
                '''
            }
        }

        stage('Install Dependencies') {
            steps {
                bat '''
                    .venv\\Scripts\\python.exe -m pip install -r requirements.txt
                '''
            }
        }

        stage('Python Code Validation') {
            steps {
                bat '.venv\\Scripts\\python.exe -m compileall -q backend'
            }
        }

        stage('Run Tests') {
            steps {
                bat '''
                    if not exist .pytest_cache mkdir .pytest_cache
                    .venv\\Scripts\\python.exe -m pytest -v --junitxml=.pytest_cache\\test-results.xml
                '''
            }
        }

        stage('Build Result') {
            steps {
                echo 'Build result: SUCCESS - dependencies, Python validation, and all tests completed successfully.'
            }
        }
    }

    post {
        always {
            junit allowEmptyResults: true, testResults: '.pytest_cache/test-results.xml'
        }
        success {
            echo 'Campus Event Ticketing Engine CI pipeline succeeded.'
        }
        failure {
            echo 'Campus Event Ticketing Engine CI pipeline failed.'
        }
    }
}
