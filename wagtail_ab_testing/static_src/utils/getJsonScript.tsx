export default (id: string) => {
    const element = document.getElementById(id);
    if (!element) {
        throw Error(`Element ${id} not found`);
    }
    return JSON.parse(element.textContent!);
};
