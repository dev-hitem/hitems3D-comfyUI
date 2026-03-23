import { app } from "../../scripts/app.js";

const SCENE_MODELS = {
    general: ["hitem3dv1.5", "hitem3dv2.0"],
    portrait: ["scene-portraitv1.5", "scene-portraitv2.0", "scene-portraitv2.1"],
};

const MODEL_RESOLUTIONS = {
    "hitem3dv1.5": ["512", "1024", "1536", "1536pro"],
    "hitem3dv2.0": ["1536", "1536pro"],
    "scene-portraitv1.5": ["1536"],
    "scene-portraitv2.0": ["1536pro"],
    "scene-portraitv2.1": ["1536pro"],
};

function getWidget(node, name) {
    return node.widgets?.find((widget) => widget.name === name);
}

function setComboValues(widget, values) {
    if (!widget) {
        return;
    }

    const nextValues = [...values];
    widget.options = widget.options || {};
    widget.options.values = nextValues;

    if (!nextValues.includes(widget.value)) {
        widget.value = nextValues[0];
    }
}

function wrapWidgetCallback(widget, onChange) {
    if (!widget) {
        return;
    }

    const originalCallback = widget.callback;
    widget.callback = function (...args) {
        const result = originalCallback?.apply(this, args);
        onChange();
        return result;
    };
}

app.registerExtension({
    name: "hitem3d.image_to_3d_linkage",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "ImageTo3DNode") {
            return;
        }

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = onNodeCreated?.apply(this, arguments);

            const sceneWidget = getWidget(this, "scene");
            const modelWidget = getWidget(this, "model");
            const resolutionWidget = getWidget(this, "resolution");

            const refreshOptions = () => {
                const scene = sceneWidget?.value || "general";
                const allowedModels = SCENE_MODELS[scene] || SCENE_MODELS.general;
                setComboValues(modelWidget, allowedModels);

                const model = modelWidget?.value || allowedModels[0];
                const allowedResolutions = MODEL_RESOLUTIONS[model] || MODEL_RESOLUTIONS[allowedModels[0]];
                setComboValues(resolutionWidget, allowedResolutions);

                this.setDirtyCanvas?.(true, true);
            };

            wrapWidgetCallback(sceneWidget, refreshOptions);
            wrapWidgetCallback(modelWidget, refreshOptions);
            refreshOptions();
            return result;
        };
    },
});
