class WineScanner {
    constructor() {
        this.video = document.getElementById('video');
        this.canvas = document.getElementById('canvas');
        this.captureButton = document.getElementById('captureButton');
        this.switchButton = document.getElementById('switchCamera');
        this.resultDiv = document.getElementById('result');
        this.wineInfoDiv = document.getElementById('wineInfo');
        this.loadingIndicator = document.getElementById('loadingIndicator');
        this.errorDiv = document.getElementById('error');

        this.currentStream = null;
        this.facingMode = 'environment';

        this.init();
    }

    async init() {
        this.addEventListeners();
        await this.startCamera();
    }

    addEventListeners() {
        this.captureButton.addEventListener('click', () => this.captureImage());
        this.switchButton.addEventListener('click', () => this.switchCamera());
    }

    async startCamera() {
        try {
            if (this.currentStream) {
                this.currentStream.getTracks().forEach(track => track.stop());
            }

            const constraints = {
                video: {
                    facingMode: this.facingMode,
                    width: { ideal: 1280 },
                    height: { ideal: 720 }
                }
            };

            this.currentStream = await navigator.mediaDevices.getUserMedia(constraints);
            this.video.srcObject = this.currentStream;

            this.hideError();
        } catch (error) {
            this.showError('Camera access denied or not available');
            console.error('Error accessing camera:', error);
        }
    }

    async switchCamera() {
        this.facingMode = this.facingMode === 'environment' ? 'user' : 'environment';
        await this.startCamera();
    }

    captureImage() {
        this.canvas.width = this.video.videoWidth;
        this.canvas.height = this.video.videoHeight;

        const context = this.canvas.getContext('2d');
        context.drawImage(this.video, 0, 0, this.canvas.width, this.canvas.height);

        const imageData = this.canvas.toDataURL('image/jpeg');
        this.analyzeImage(imageData);
    }

    async analyzeImage(imageData) {
        this.showLoading();
        this.hideError();
        this.hideResult();

        try {
            const response = await fetch('/analyze', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ image: imageData })
            });

            if (!response.ok) {
                throw new Error('Analysis failed');
            }

            const result = await response.json();
            this.displayResult(result);
        } catch (error) {
            this.showError('Failed to analyze image. Please try again.');
            console.error('Analysis error:', error);
        } finally {
            this.hideLoading();
        }
    }

    displayResult(result) {
        if (result.error) {
            this.showError(result.error);
            return;
        }

        let html = '';
        if (result.wineInfo) {
            const wine = result.wineInfo;
            html = `
                <div class="wine-info-item">
                    <h3>${wine.name}</h3>
                    <p><strong>Producer:</strong> ${wine.producer}</p>
                    <p><strong>Region:</strong> ${wine.region}</p>
                    <p><strong>Vintage:</strong> ${wine.vintage}</p>
                    <p><strong>Varietal:</strong> ${wine.varietal}</p>
                    <p><strong>Description:</strong> ${wine.description}</p>
                </div>
            `;
        } else {
            html = '<p>No wine information found. Please try again.</p>';
        }

        this.wineInfoDiv.innerHTML = html;
        this.showResult();
    }

    showLoading() {
        this.loadingIndicator.style.display = 'block';
    }

    hideLoading() {
        this.loadingIndicator.style.display = 'none';
    }

    showError(message) {
        this.errorDiv.textContent = message;
        this.errorDiv.style.display = 'block';
    }

    hideError() {
        this.errorDiv.style.display = 'none';
    }

    showResult() {
        this.resultDiv.style.display = 'block';
    }

    hideResult() {
        this.resultDiv.style.display = 'none';
    }
}

// Initialize the app when the DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new WineScanner();
});
