var socket = io();
var mediaRecorder;
var audioChunks = [];

// Scroll chat to the bottom initially
document.addEventListener('DOMContentLoaded', (event) => {
    var chatHistory = document.querySelector('.chat-history');
    chatHistory.scrollTop = chatHistory.scrollHeight;
});

// Scroll to the bottom function for new messages
function scrollToBottom() {
    var chatHistory = document.querySelector('.chat-history');
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

// Listen for new chat updates
socket.on('update_chat', function(data) {
    var chatHistory = document.querySelector('.chat-history');
    chatHistory.innerHTML = '';  // Clear current chat history

    data.chat_history.forEach(function(message) {
        var nameClass = message.sender === 'Alice' ? 'name-chatbot' : 'name-user';
        chatHistory.innerHTML += `<p><strong class="${nameClass}">${message.sender}:</strong> ${message.message}</p>`;
    });

    scrollToBottom(); // Scroll to the bottom
});

// Listen for audio responses
socket.on('new_audio_response', function(data) {
    var chatHistory = document.querySelector('.chat-history');
    var nameClass = 'name-chatbot';
    chatHistory.innerHTML += `<p><strong class="${nameClass}">Alice:</strong> ${data.message}</p>`;
    scrollToBottom();

    // Play audio response
    var audio = new Audio(data.audio_path);
    audio.play();
});

// Initialize audio recording
navigator.mediaDevices.getUserMedia({ audio: true })
    .then(function(stream) {
        mediaRecorder = new MediaRecorder(stream);
        mediaRecorder.ondataavailable = function(event) {
            audioChunks.push(event.data);
        };
    })
    .catch(function(error) {
        console.error('Error accessing microphone:', error);
    });

// Start recording on 'mousedown'
document.getElementById('talk-button').addEventListener('mousedown', function() {
    if (mediaRecorder) {
        audioChunks = []; // Reset audio chunks
        mediaRecorder.start();
        console.log('Recording started');
    }
});

// Stop recording on 'mouseup' and send to server
document.getElementById('talk-button').addEventListener('mouseup', function() {
    if (mediaRecorder && mediaRecorder.state === 'recording') {
        mediaRecorder.stop(); // Stop recording
        console.log('Recording stopped');

        mediaRecorder.onstop = function() {
            var audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
            audioChunks = []; // Reset for next recording

            var formData = new FormData();
            formData.append('audio', audioBlob, 'recording.wav');

            fetch('/process_audio', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                console.log('Server response:', data);
                handleServerResponse(data);
            })
            .catch(error => console.error('Error:', error));
        };
    }
});

// Handle server response after processing audio
function handleServerResponse(data) {
    var chatHistory = document.querySelector('.chat-history');
    var nameClass = 'name-chatbot';
    chatHistory.innerHTML += `<p><strong class="${nameClass}">Alice:</strong> ${data.message}</p>`;
    scrollToBottom();

    // Play the audio response
    var audio = new Audio(data.audio_path);
    audio.play();
}
