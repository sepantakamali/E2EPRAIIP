from src.textclf.model import build_pipeline
pipe = build_pipeline(max_features=1000, max_iter=100)
print(pipe)