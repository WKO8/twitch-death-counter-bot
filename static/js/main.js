document.addEventListener('DOMContentLoaded', (event) => {
    const socket = io();
    socket.on('update_death_count', (data) => {
        document.getElementById('death-counter').textContent = `Deaths: ${data.death_count}`;
    });
});