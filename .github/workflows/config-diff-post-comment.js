module.exports = async ({ github, context, core, configDiff }) => {
    try {
        // Check if the structure matches {"added": {}, "deleted": {}, "modified": {}}
        // Do not create comment if there are no configuration changes
        // const isEmptyDiff = Object.keys(configDiff.added).length === 0 &&
        //   Object.keys(configDiff.deleted).length === 0 &&
        //   Object.keys(configDiff.modified).length === 0;
    
        if (!configDiff) {
          console.log("No changes detected. Skipping comment creation.");
          return;
        }
    
        // const diffOutput = JSON.stringify(configDiff, null, 2);
        const commentBody = `
### Config Diff Tool Output

\`\`\`

${configDiff}

\`\`\`
  
  
The above configuration changes are found in the PR. Please update the relevant release documentation if necessary.
    `;
    
        const { owner, repo } = context.repo;
        const issueNumber = context.payload.pull_request.number;
    
        const comments = await github.paginate(
          github.rest.issues.listComments, {
            owner,
            repo,
            issue_number: issueNumber,
            per_page: 100,
          }
        );
    
        const existingComment = comments.find(comment => comment.body.includes("### Config Diff Tool Output"));
    
        if (existingComment) {
          console.log("A config diff comment already exists, deleting it...");
          // Update the existing comment
          await github.rest.issues.deleteComment({
            comment_id: existingComment.id,
            owner,
            repo,
          });
        }
    
        console.log("Creating a new config diff comment...");
        // Create a new comment
        await github.rest.issues.createComment({
          issue_number: issueNumber,
          owner,
          repo,
          body: commentBody,
        });
    
        // Set the status as FAILED if any configuration changes are detected
        console.log("Configuration changes detected: ",  configDiff);
        core.setFailed("Configuration Changes Detected, Update release documents - if necessary");
      } catch (error) {
        core.setFailed(error.message);
      }
}