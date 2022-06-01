const Toast = Swal.mixin({
    toast: true,
    position: 'top-end',
    showConfirmButton: false,
    timer: 3000,
    timerProgressBar: true,
    didOpen: (toast) => {
        toast.addEventListener('mouseenter', Swal.stopTimer)
        toast.addEventListener('mouseleave', Swal.resumeTimer)
    }
})

const showMessage = (title = '', icon = 'success') => {
    Toast.fire({
        icon,
        title,
    })
}

const _uuidv4 = () => {
    return ([1e7] + -1e3 + -4e3 + -8e3 + -1e11).replace(/[018]/g, c =>
        (c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16)
    );
}

const stringToColor = (v) => {
    let hash = 0;
    for (let i = 0; i < v.length; i++) {
        hash = v.charCodeAt(i) + ((hash << 5) - hash);
    }

    let color = '#';
    for (let i = 0; i < 3; i++) {
        let value = (hash >> (i * 8)) & 0xFF;
        color += (value.toString(16)).slice(-2).padStart(2, '0');
    }
    return color;
}

const invertColor = (color) => {
    return '#' + (Number(`0x1${color.slice(1)}`) ^ 0xFFFFFF).toString(16).slice(1).toUpperCase()
}

const intComma = (v) => {
    return v.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}