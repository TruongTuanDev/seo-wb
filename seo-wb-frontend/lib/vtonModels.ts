export interface VtonModel {
  id: string;
  name: string;
  gender: "Female" | "Male";
  bodyType: string;
  height: number;
  weight: number;
  frontImageUrl: string;
  backImageUrl?: string;
  imageUrl: string; // compatibility wrapper
  label: string;
  description: string;
  availablePoses?: string[];
  isAiGenerated?: boolean;
}

export const VTON_MODELS: VtonModel[] = [
  {
    id: "model_1",
    name: "Model 1",
    gender: "Female",
    bodyType: "Petite",
    height: 155,
    weight: 45,
    frontImageUrl: "/models/model1.JPG",
    imageUrl: "/models/model1.JPG",
    label: "Female – Petite",
    description: "Height: 155cm • Weight: 45kg",
    availablePoses: ["front", "side_45", "walking", "hand_on_hip", "sitting", "back"]
  },
  {
    id: "model_2",
    name: "Model 2",
    gender: "Female",
    bodyType: "Slim",
    height: 170,
    weight: 52,
    frontImageUrl: "/models/model2.png",
    imageUrl: "/models/model2.png",
    label: "Female – Slim",
    description: "Height: 170cm • Weight: 52kg",
    availablePoses: ["front", "side_45", "walking", "hand_on_hip", "sitting", "back"]
  },
  {
    id: "model_3",
    name: "Model 3",
    gender: "Female",
    bodyType: "Average",
    height: 165,
    weight: 60,
    frontImageUrl: "/models/model3.png",
    imageUrl: "/models/model3.png",
    label: "Female – Average",
    description: "Height: 165cm • Weight: 60kg",
    availablePoses: ["front"],
    isAiGenerated: true
  },
  {
    id: "model_4",
    name: "Model 4",
    gender: "Female",
    bodyType: "Curvy",
    height: 170,
    weight: 72,
    frontImageUrl: "/models/model4.png",
    imageUrl: "/models/model4.png",
    label: "Female – Curvy",
    description: "Height: 170cm • Weight: 72kg",
    availablePoses: ["front"],
    isAiGenerated: true
  },
  {
    id: "model_5",
    name: "Model 5",
    gender: "Female",
    bodyType: "Plus Size",
    height: 175,
    weight: 85,
    frontImageUrl: "/models/model5.png",
    imageUrl: "/models/model5.png",
    label: "Female – Plus Size",
    description: "Height: 175cm • Weight: 85kg",
    availablePoses: ["front"],
    isAiGenerated: true
  },
  {
    id: "model_6",
    name: "Model 6",
    gender: "Male",
    bodyType: "Slim",
    height: 180,
    weight: 68,
    frontImageUrl: "/models/model6.png",
    imageUrl: "/models/model6.png",
    label: "Male – Slim",
    description: "Height: 180cm • Weight: 68kg",
    availablePoses: ["front"]
  },
  {
    id: "model_7",
    name: "Model 7",
    gender: "Male",
    bodyType: "Average",
    height: 178,
    weight: 78,
    frontImageUrl: "/models/model7.png",
    imageUrl: "/models/model7.png",
    label: "Male – Average",
    description: "Height: 178cm • Weight: 78kg",
    availablePoses: ["front"]
  },
  {
    id: "model_8",
    name: "Model 8",
    gender: "Male",
    bodyType: "Athletic",
    height: 185,
    weight: 88,
    frontImageUrl: "/models/model8.png",
    imageUrl: "/models/model8.png",
    label: "Male – Athletic",
    description: "Height: 185cm • Weight: 88kg",
    availablePoses: ["front"]
  },
  {
    id: "model_9",
    name: "Model 9",
    gender: "Male",
    bodyType: "Heavy",
    height: 182,
    weight: 105,
    frontImageUrl: "/models/model9.png",
    imageUrl: "/models/model9.png",
    label: "Male – Heavy",
    description: "Height: 182cm • Weight: 105kg",
    availablePoses: ["front"],
    isAiGenerated: true
  },
  {
    id: "model_10",
    name: "Model 10",
    gender: "Male",
    bodyType: "Solid",
    height: 188,
    weight: 92,
    frontImageUrl: "/models/model10.png",
    imageUrl: "/models/model10.png",
    label: "Male – Solid",
    description: "Height: 188cm • Weight: 92kg",
    availablePoses: ["front"],
    isAiGenerated: true
  }
];
