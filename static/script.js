const form = document.getElementById("uploadForm");
const fileInput = document.getElementById("fileInput");
const formatSelect = document.getElementById("formatSelect");
const convertBtn = document.getElementById("convertBtn");
const loading = document.getElementById("loading");
const downloadSection = document.getElementById("downloadSection");
const downloadBtn = document.getElementById("downloadBtn");
const errorSection = document.getElementById("errorSection");
const errorMsg = document.getElementById("errorMsg");

// Navbar hamburger toggle
const hamburger = document.querySelector(".hamburger");
const navLinks = document.querySelector(".nav-links");

if (hamburger) {
  hamburger.addEventListener("click", () => {
    navLinks.classList.toggle("active");
    hamburger.classList.toggle("active");
  });
}

if (fileInput) {
  fileInput.addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (!file) {
      formatSelect.innerHTML = "";
      formatSelect.disabled = true;
      convertBtn.disabled = true;
      return;
    }

    const ext = file.name.split(".").pop().toLowerCase();
    formatSelect.innerHTML = ""; // Clear options
    let options = [];

    if (["jpg", "jpeg", "png", "webp", "bmp", "gif", "tiff"].includes(ext)) {
      options = ["png", "jpg", "jpeg", "webp", "pdf"].filter((opt) => opt !== ext);
      if (options.length === 0) {
        options = ["png", "jpg", "jpeg", "webp", "pdf"];
      }
    } else if (ext === "docx") {
      options = ["pdf"];
    } else if (ext === "pdf") {
      options = ["docx", "png", "jpg"];
    }

    if (options.length === 0) {
      errorSection.classList.remove("hidden");
      errorMsg.textContent = "Unsupported file type. Please upload an image (JPG, PNG, WEBP, etc.), DOCX, or PDF.";
      formatSelect.disabled = true;
      convertBtn.disabled = true;
    } else {
      errorSection.classList.add("hidden");
      options.forEach((opt) => {
        const option = document.createElement("option");
        option.value = opt;
        option.text = opt.toUpperCase();
        formatSelect.add(option);
      });
      formatSelect.disabled = false;
      convertBtn.disabled = false;
    }
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    loading.classList.remove("hidden");
    downloadSection.classList.add("hidden");
    errorSection.classList.add("hidden");

    const formData = new FormData(form);

    try {
      const response = await fetch("/convert", {
        method: "POST",
        body: formData,
      });

      const result = await response.json();
      loading.classList.add("hidden");

      if (result.download_url) {
        downloadBtn.href = result.download_url;
        downloadSection.classList.remove("hidden");
      } else {
        errorSection.classList.remove("hidden");
        errorMsg.textContent = "Error: " + result.error;
      }
    } catch (err) {
      loading.classList.add("hidden");
      errorSection.classList.remove("hidden");
      errorMsg.textContent = "Something went wrong! Please try again.";
    }
  });
}


// Trigger animations on load
window.addEventListener('load', () => {
  document.querySelectorAll('.animate-fade-in, .animate-slide-up, .animate-fade-in-delay').forEach(el => {
    el.style.opacity = 1;
    el.style.transform = 'translateY(0)';
  });
});