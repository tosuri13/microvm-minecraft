ARTIFACT_DIR := artifact

.PHONY: build clean deploy

build: clean
	mkdir -p $(ARTIFACT_DIR)/apps/microvm
	cp Dockerfile $(ARTIFACT_DIR)/
	cp -r apps/microvm $(ARTIFACT_DIR)/apps/
	uv pip compile pyproject.toml -o $(ARTIFACT_DIR)/requirements.txt

clean:
	rm -rf $(ARTIFACT_DIR)

deploy: build
	cd cdk && cdk deploy
