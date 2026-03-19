import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

app.registerExtension({
    name: "hitems3d.load_glb_upload",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "LoadGLBNode") {
            return;
        }

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = onNodeCreated?.apply(this, arguments);
            const node = this;
            const comboWidget = node.widgets?.find((w) => w.name === "model_file");

            const uploadWidget = node.addWidget("button", "upload_glb", "upload", () => {
                const input = document.createElement("input");
                input.type = "file";
                input.accept = ".glb";
                input.style.display = "none";
                input.onchange = async () => {
                    const file = input.files?.[0];
                    if (!file) return;

                    const formData = new FormData();
                    formData.append("image", file);
                    formData.append("type", "input");

                    try {
                        const resp = await api.fetchApi("/upload/image", {
                            method: "POST",
                            body: formData,
                        });

                        if (resp.status !== 200) {
                            alert("Upload failed: " + resp.statusText);
                            return;
                        }

                        const data = await resp.json();
                        const filename = data.subfolder
                            ? `${data.subfolder}/${data.name}`
                            : data.name;

                        if (comboWidget) {
                            if (!comboWidget.options.values.includes(filename)) {
                                comboWidget.options.values.push(filename);
                            }
                            comboWidget.value = filename;
                            comboWidget.callback?.(filename);
                        }
                    } catch (e) {
                        console.error("GLB upload error:", e);
                        alert("Upload failed: " + e.message);
                    }

                    input.remove();
                };

                document.body.appendChild(input);
                input.click();
            });

            uploadWidget.label = "Upload GLB File";
            uploadWidget.serialize = false;

            return result;
        };
    },
});
